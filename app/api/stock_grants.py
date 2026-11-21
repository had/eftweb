"""Stock-based grants, independent of the legacy project portfolios."""

import hashlib
import json
from datetime import date
from uuid import UUID

from flask import current_app, jsonify, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import db
from app.stocks.models import GrantVesting, Stock, StockGrant, StockSaleAllocation
from app.stocks.validation import (
    calendar_date,
    grant_number_value,
    grant_payload,
    grant_tax_details,
)

from . import api
from .stock_transactions import stock_write


def active_stock(stock_id):
    stock = db.session.get(Stock, stock_id)
    if stock is None:
        return None, (jsonify({"error": "Stock not found"}), 404)
    if stock.is_archived or stock.family.is_archived:
        return None, (jsonify({"error": "Stock or family is archived"}), 410)
    return stock, None


def replay_grant(grant, request_hash):
    if grant.request_hash != request_hash:
        return (
            jsonify(
                {
                    "error": "This creation token was already used for different grant data. Reload to review the saved grant."
                }
            ),
            409,
        )
    return jsonify(grant.to_dict()), 200


@api.route("/api/stocks/<int:stock_id>", methods=["GET"])
def get_stock(stock_id):
    stock, error = active_stock(stock_id)
    if error:
        return error
    return jsonify(stock.to_dict())


@api.route("/api/stocks/<int:stock_id>/grants", methods=["GET", "POST"])
def stock_grants(stock_id):
    if request.method == "GET":
        stock, error = active_stock(stock_id)
        if error:
            return error
        return jsonify([grant.to_dict() for grant in stock.grants])
    try:
        with stock_write(stock_id):
            stock, error = active_stock(stock_id)
            if error:
                return error
            return create_stock_grant(stock)
    except SQLAlchemyError:
        current_app.logger.exception("Could not save grant")
        return jsonify({"error": "Could not save the grant. Please try again."}), 500


def create_stock_grant(stock):
    try:
        token = str(UUID(request.headers.get("Idempotency-Key", "")))
    except (ValueError, AttributeError):
        return jsonify({"error": "A UUID Idempotency-Key header is required"}), 400
    try:
        data = grant_payload(request.get_json(silent=True), stock)
    except ValueError as validation_error:
        return jsonify({"error": str(validation_error)}), 400
    request_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    existing = StockGrant.query.filter_by(stock_id=stock.id, creation_token=token).first()
    if existing:
        return replay_grant(existing, request_hash)
    if (
        data.get("grant_number")
        and StockGrant.query.filter_by(stock_id=stock.id, grant_number=data["grant_number"]).first()
    ):
        return jsonify({"error": "This grant number already exists for this stock"}), 409
    rows = data.pop("vestings")
    grant = StockGrant(
        stock_id=stock.id,
        **{
            **data,
            "grant_date": date.fromisoformat(data["grant_date"]),
            **(
                {"approval_date": date.fromisoformat(data["approval_date"])}
                if data.get("approval_date")
                else {}
            ),
            "vesting_start_date": date.fromisoformat(data["vesting_start_date"]),
        },
        creation_token=token,
        request_hash=request_hash,
        vestings=[
            GrantVesting(date=date.fromisoformat(row["date"]), quantity=row["quantity"])
            for row in rows
        ],
    )
    db.session.add(grant)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = StockGrant.query.filter_by(stock_id=stock.id, creation_token=token).first()
        if existing:
            return replay_grant(existing, request_hash)
        current_app.logger.exception("Could not save grant")
        return jsonify({"error": "Could not save the grant. Please try again."}), 500
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not save grant")
        return jsonify({"error": "Could not save the grant. Please try again."}), 500
    return jsonify(grant.to_dict()), 201


@api.route("/api/stocks/<int:stock_id>/grants/<int:grant_id>", methods=["DELETE"])
def delete_stock_grant(stock_id, grant_id):
    try:
        with stock_write(stock_id):
            _, error = active_stock(stock_id)
            if error:
                return error
            grant = StockGrant.query.filter_by(id=grant_id, stock_id=stock_id).first()
            if grant is None:
                return jsonify({"error": "Grant not found for this stock"}), 404
            has_sales = (
                StockSaleAllocation.query.join(
                    GrantVesting, StockSaleAllocation.vesting_id == GrantVesting.id
                )
                .filter(GrantVesting.grant_id == grant_id)
                .first()
            )
            if has_sales:
                return (
                    jsonify(
                        {
                            "error": "This grant has recorded sales. Delete those sales before deleting the grant."
                        }
                    ),
                    409,
                )
            db.session.delete(grant)
            db.session.commit()
            return "", 204
    except SQLAlchemyError:
        current_app.logger.exception("Could not delete grant")
        return jsonify({"error": "Could not delete the grant. Please try again."}), 500


@api.route("/api/stocks/<int:stock_id>/grants/<int:grant_id>", methods=["PATCH"])
def edit_stock_grant(stock_id, grant_id):
    try:
        with stock_write(stock_id):
            stock, error = active_stock(stock_id)
            if error:
                return error
            grant = StockGrant.query.filter_by(id=grant_id, stock_id=stock_id).first()
            if grant is None:
                return jsonify({"error": "Grant not found for this stock"}), 404
            data = request.get_json(silent=True)
            allowed = {"title", "grant_number", "grant_date", "approval_date", "taxpayer_role"}
            if not isinstance(data, dict) or not data or set(data) - allowed:
                return (
                    jsonify({"error": "Provide grant title, number, dates and/or taxpayer only"}),
                    400,
                )
            try:
                updates = {}
                if "grant_date" in data:
                    updates["grant_date"] = calendar_date(data["grant_date"], "Grant date")
                if "title" in data:
                    title = data["title"]
                    if not isinstance(title, str) or len(title.strip()) > 256:
                        raise ValueError("Grant title must be a string of at most 256 characters")
                    effective_date = updates.get("grant_date", grant.grant_date)
                    updates["title"] = (
                        title.strip() or f"{stock.symbol}-{effective_date.isoformat()}"
                    )
                if "grant_number" in data:
                    updates["grant_number"] = grant_number_value(data["grant_number"])
                tax_details = grant_tax_details(data, stock)
                if "approval_date" in data:
                    updates["approval_date"] = (
                        date.fromisoformat(tax_details["approval_date"])
                        if tax_details.get("approval_date")
                        else None
                    )
                if "taxpayer_role" in data:
                    updates["taxpayer_role"] = tax_details.get("taxpayer_role")
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
            for field, value in updates.items():
                setattr(grant, field, value)
            db.session.commit()
            return jsonify(grant.to_dict())
    except IntegrityError:
        return jsonify({"error": "This grant number already exists for this stock"}), 409
    except SQLAlchemyError:
        current_app.logger.exception("Could not update grant")
        return jsonify({"error": "Could not update the grant. Please try again."}), 500
