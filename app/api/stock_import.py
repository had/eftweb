"""Preview and confirm XLSX imports without storing uploaded files."""

import hashlib
import json
from uuid import UUID

from flask import current_app, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from werkzeug.exceptions import RequestEntityTooLarge

from app import db
from app.stocks.import_parsers import MAX_UPLOAD, fingerprint, parse_workbook
from app.stocks.import_service import persist_import, prepare_import, stock_snapshot
from app.stocks.models import Stock, StockImportReceipt

from . import api
from .stock_grants import active_stock
from .stock_transactions import stock_write


def uploaded_workbook():
    request.max_content_length = MAX_UPLOAD + 1024 * 1024  # multipart overhead
    upload = request.files.get("file")
    if upload is None or not upload.filename or not upload.filename.lower().endswith(".xlsx"):
        raise ValueError("Choose an XLSX workbook")
    content = upload.stream.read(MAX_UPLOAD + 1)
    try:
        return content, parse_workbook(content)
    except (ValueError, TypeError, OverflowError):
        raise
    except Exception as error:
        # XML/parser failures from an untrusted workbook must also be JSON errors.
        raise ValueError(
            "Could not read this workbook. Choose a valid, unencrypted XLSX file."
        ) from error


@api.route("/api/stocks/<int:stock_id>/import/preview", methods=["POST"])
def preview_stock_import(stock_id):
    try:
        content, parsed = uploaded_workbook()
        with (
            db.engine.connect().execution_options(isolation_level="SERIALIZABLE") as connection,
            Session(bind=connection) as session,
        ):
            if connection.dialect.name == "sqlite":
                session.execute(text("BEGIN"))
            stock = session.get(Stock, stock_id)
            if stock is None:
                return jsonify({"error": "Stock not found"}), 404
            if stock.is_archived or stock.family.is_archived:
                return jsonify({"error": "Stock or family is archived"}), 410
            preview = prepare_import(parsed, stock_snapshot(stock))
        preview["file_digest"] = hashlib.sha256(content).hexdigest()
        return jsonify(preview)
    except RequestEntityTooLarge:
        return jsonify({"error": "Choose an XLSX file no larger than 10 MiB"}), 413
    except (ValueError, TypeError, OverflowError) as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        current_app.logger.exception("Could not preview stock import")
        return (
            jsonify({"error": "Could not read this workbook. Check that it is a valid XLSX file."}),
            400,
        )


@api.route("/api/stocks/<int:stock_id>/import", methods=["POST"])
def confirm_stock_import(stock_id):
    try:
        content, parsed = uploaded_workbook()
        try:
            token = str(UUID(request.headers.get("Idempotency-Key", "")))
        except (ValueError, AttributeError):
            raise ValueError("A UUID Idempotency-Key header is required") from None
        try:
            decisions = json.loads(request.form.get("decisions", "{}"))
        except (ValueError, TypeError):
            raise ValueError("Import decisions must be valid JSON") from None
        revision = request.form.get("stock_revision", "")
        request_hash = fingerprint(
            {
                "file": hashlib.sha256(content).hexdigest(),
                "decisions": decisions,
                "revision": revision,
            }
        )
        with stock_write(stock_id):
            stock, error = active_stock(stock_id)
            if error:
                return error
            receipt = StockImportReceipt.query.filter_by(
                stock_id=stock_id, creation_token=token
            ).first()
            if receipt:
                if receipt.request_hash != request_hash:
                    return (
                        jsonify({"error": "This import token was already used for different data"}),
                        409,
                    )
                return jsonify(receipt.result), 200
            # Reload relationships rather than trusting state from an earlier request.
            db.session.expire_all()
            snapshot = stock_snapshot(stock)
            if revision != fingerprint(snapshot):
                return (
                    jsonify({"error": "Stock data changed after preview. Preview the file again."}),
                    409,
                )
            preview = prepare_import(parsed, snapshot, decisions, confirming=True)
            if not preview["can_import"]:
                return (
                    jsonify(
                        {
                            "error": "Resolve or skip all selected sale issues before importing",
                            "preview": preview,
                        }
                    ),
                    400,
                )
            result = {"format": parsed["format"], "counts": persist_import(stock, parsed, preview)}
            db.session.add(
                StockImportReceipt(
                    stock_id=stock_id,
                    creation_token=token,
                    request_hash=request_hash,
                    result=result,
                )
            )
            db.session.commit()
            return jsonify(result), 201
    except RequestEntityTooLarge:
        return jsonify({"error": "Choose an XLSX file no larger than 10 MiB"}), 413
    except (ValueError, TypeError, OverflowError) as error:
        return jsonify({"error": str(error)}), 400
    except SQLAlchemyError:
        current_app.logger.exception("Could not commit stock import")
        return (
            jsonify(
                {"error": "Could not save this import. No records were imported. Please try again."}
            ),
            500,
        )
