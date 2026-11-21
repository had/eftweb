"""Stock tax previews, atomic acceptance and independently editable source statements."""

from uuid import UUID

from flask import current_app, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.family.models import (
    CapitalGainHelperLine,
    CapitalGainStatement,
    StockTaxReceipt,
    TaxReturn,
)
from app.service.stock_tax import aggregate, prepare, reported_values
from app.stocks.import_parsers import fingerprint

from . import api


def active_return(tax_return_id):
    result = db.session.get(TaxReturn, tax_return_id)
    if result is None:
        return None, (jsonify(error="Tax return not found"), 404)
    if result.is_archived or result.family.is_archived:
        return None, (jsonify(error="Tax return or family is archived"), 410)
    if not result.has_stock_statements:
        return None, (jsonify(error="Stock gains/losses are not enabled for this tax return"), 409)
    return result, None


def lock_return(tax_return_id):
    if db.engine.dialect.name == "sqlite":
        db.session.execute(text("BEGIN IMMEDIATE"))
    else:
        db.session.query(TaxReturn).filter_by(id=tax_return_id).with_for_update().first()


def listing(tax_return):
    statements = (
        CapitalGainStatement.query.filter_by(tax_return_id=tax_return.id)
        .order_by(CapitalGainStatement.id)
        .all()
    )
    return {"statements": [s.to_dict() for s in statements], "aggregate": aggregate(statements)}


@api.route("/api/tax-returns/<int:tax_return_id>/capital-gain-statements", methods=["GET", "POST"])
def capital_statements(tax_return_id):
    try:
        if request.method == "POST":
            lock_return(tax_return_id)
        tax_return, error = active_return(tax_return_id)
        if error:
            return error
        if request.method == "GET":
            return jsonify(listing(tax_return))
        data = request.get_json(silent=True)
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("title"), str)
            or not 0 < len(data["title"].strip()) <= 256
        ):
            raise ValueError("A source name is required (up to 256 characters)")
        if "capital_result" not in data:
            raise ValueError("A signed whole EUR capital gain/loss is required")
        reported = reported_values({"capital_result": data["capital_result"]})
        statement = CapitalGainStatement(
            tax_return_id=tax_return.id,
            title=data["title"].strip(),
            computed={},
            reported=reported,
            metadata_snapshot={},
        )
        db.session.add(statement)
        db.session.commit()
        return jsonify(statement.to_dict(details=True)), 201
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except SQLAlchemyError:
        current_app.logger.exception("Could not save capital gain source")
        return jsonify(error="Could not save source. Please try again."), 500
    finally:
        if request.method != "GET":
            db.session.rollback()


@api.route(
    "/api/tax-returns/<int:tax_return_id>/capital-gain-statements/<int:statement_id>",
    methods=["GET", "PUT", "DELETE"],
)
def capital_statement(tax_return_id, statement_id):
    try:
        if request.method != "GET":
            lock_return(tax_return_id)
        tax_return, error = active_return(tax_return_id)
        if error:
            return error
        statement = CapitalGainStatement.query.filter_by(
            id=statement_id, tax_return_id=tax_return.id
        ).first()
        if statement is None:
            return jsonify(error="Statement not found for this tax return"), 404
        if request.method == "GET":
            return jsonify(statement.to_dict(details=True))
        if request.method == "DELETE":
            db.session.delete(statement)
            db.session.commit()
            return "", 204
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) - {"title", "reported"}:
            raise ValueError("Provide title and/or reported contributions")
        if "title" in data:
            if not isinstance(data["title"], str) or not 0 < len(data["title"].strip()) <= 256:
                raise ValueError("A source name is required (up to 256 characters)")
            statement.title = data["title"].strip()
        if "reported" in data:
            if statement.source_key is None and set(data["reported"]) - {"capital_result"}:
                raise ValueError("Manual sources support capital gain/loss only")
            statement.reported = reported_values(data["reported"], statement.reported)
        db.session.commit()
        return jsonify(statement.to_dict(details=True))
    except (ValueError, TypeError) as error:
        return jsonify(error=str(error)), 400
    except SQLAlchemyError:
        current_app.logger.exception("Could not update capital gain source")
        return jsonify(error="Could not update source. Please try again."), 500
    finally:
        if request.method != "GET":
            db.session.rollback()


@api.route("/api/tax-returns/<int:tax_return_id>/stock-tax/preview", methods=["POST"])
def stock_tax_preview(tax_return_id):
    tax_return, error = active_return(tax_return_id)
    if error:
        return error
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) - {"fx_overrides"}:
        return jsonify(error="Provide an object with optional fx_overrides"), 400
    try:
        return jsonify(prepare(tax_return, data.get("fx_overrides")))
    except ValueError as error:
        return jsonify(error=str(error)), 400


@api.route("/api/tax-returns/<int:tax_return_id>/stock-tax/accept", methods=["POST"])
def stock_tax_accept(tax_return_id):
    try:
        # FX refresh belongs to preview. Acceptance never fetches or commits rates mid-transaction.
        lock_return(tax_return_id)
        tax_return, error = active_return(tax_return_id)
        if error:
            return error
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) - {
            "source_revision",
            "fx_overrides",
            "reported",
            "replace_existing",
        }:
            raise ValueError("Invalid acceptance payload")
        token = str(UUID(request.headers.get("Idempotency-Key", "")))
        request_hash = fingerprint(data)
        receipt = StockTaxReceipt.query.filter_by(tax_return_id=tax_return.id, token=token).first()
        if receipt:
            if receipt.request_hash != request_hash:
                return jsonify(error="This acceptance key was already used for different data"), 409
            return jsonify(receipt.result), 200
        preview = prepare(tax_return, data.get("fx_overrides"), refresh=False)
        if data.get("source_revision") != preview["source_revision"]:
            return (
                jsonify(error="Stock data, rates or saved statements changed. Prepare again."),
                409,
            )
        if not preview["can_accept"]:
            return (
                jsonify(
                    error="Complete the missing tax inputs before accepting",
                    errors=preview["errors"],
                ),
                422,
            )
        if preview["replacements"] and data.get("replace_existing") is not True:
            return jsonify(error="Confirm replacement/removal of existing stock statements"), 409
        edits = data.get("reported", {})
        known = {str(s["stock_id"]) for s in preview["statements"]}
        if not isinstance(edits, dict) or set(edits) - known:
            raise ValueError("Reported edits must match stocks in this preparation")
        # Validate everything before replacing even one saved statement.
        for proposed in preview["statements"]:
            proposed["reported"] = reported_values(
                edits.get(str(proposed["stock_id"]), {}), proposed["computed"]
            )
        for statement in CapitalGainStatement.query.filter(
            CapitalGainStatement.tax_return_id == tax_return.id,
            CapitalGainStatement.source_key.isnot(None),
        ).all():
            db.session.delete(statement)
        db.session.flush()
        for proposed in preview["statements"]:
            statement = CapitalGainStatement(
                tax_return_id=tax_return.id,
                title=proposed["title"],
                source_key=proposed["source_key"],
                stock_id=proposed["stock_id"],
                computed=proposed["computed"],
                reported=proposed["reported"],
                metadata_snapshot={**proposed["metadata"], "threshold": preview["threshold"]},
                lines=[
                    CapitalGainHelperLine(position=i, data=line)
                    for i, line in enumerate(proposed["lines"])
                ],
            )
            db.session.add(statement)
        db.session.flush()
        result = listing(tax_return)
        db.session.add(
            StockTaxReceipt(
                tax_return_id=tax_return.id, token=token, request_hash=request_hash, result=result
            )
        )
        db.session.commit()
        return jsonify(result), 201
    except (ValueError, TypeError, AttributeError) as error:
        return jsonify(error=str(error)), 400
    except SQLAlchemyError:
        current_app.logger.exception("Could not accept stock preparation")
        return jsonify(error="Could not save preparation. No statements changed."), 500
    finally:
        db.session.rollback()
