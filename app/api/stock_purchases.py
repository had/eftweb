"""Completed stock purchases, including employee stock purchase plans."""

import hashlib
import json
from datetime import date
from uuid import UUID

from flask import current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.stocks.models import StockPurchase, StockSaleAllocation
from app.stocks.validation import purchase_payload

from . import api
from .stock_grants import active_stock
from .stock_transactions import stock_write


@api.route("/api/stocks/<int:stock_id>/purchases", methods=["GET", "POST"])
def stock_purchases(stock_id):
    if request.method == "GET":
        stock, error = active_stock(stock_id)
        if error:
            return error
        return jsonify([purchase.to_dict() for purchase in stock.purchases])
    try:
        with stock_write(stock_id):
            stock, error = active_stock(stock_id)
            if error:
                return error
            try:
                token = str(UUID(request.headers.get("Idempotency-Key", "")))
            except (ValueError, AttributeError):
                return jsonify({"error": "A UUID Idempotency-Key header is required"}), 400
            try:
                data = purchase_payload(request.get_json(silent=True))
            except ValueError as validation_error:
                return jsonify({"error": str(validation_error)}), 400
            request_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
            existing = StockPurchase.query.filter_by(
                stock_id=stock_id, creation_token=token
            ).first()
            if existing:
                if existing.request_hash != request_hash:
                    return (
                        jsonify(
                            {
                                "error": "This creation token was already used for different purchase data. Reload to review the saved purchase."
                            }
                        ),
                        409,
                    )
                return jsonify(existing.to_dict()), 200
            purchase = StockPurchase(
                stock_id=stock.id,
                **{**data, "purchase_date": date.fromisoformat(data["purchase_date"])},
                creation_token=token,
                request_hash=request_hash,
            )
            db.session.add(purchase)
            db.session.commit()
            return jsonify(purchase.to_dict()), 201
    except SQLAlchemyError:
        current_app.logger.exception("Could not save purchase")
        return jsonify({"error": "Could not save the purchase. Please try again."}), 500


@api.route("/api/stocks/<int:stock_id>/purchases/<int:purchase_id>", methods=["DELETE"])
def delete_stock_purchase(stock_id, purchase_id):
    try:
        with stock_write(stock_id):
            _, error = active_stock(stock_id)
            if error:
                return error
            purchase = StockPurchase.query.filter_by(id=purchase_id, stock_id=stock_id).first()
            if purchase is None:
                return jsonify({"error": "Purchase not found for this stock"}), 404
            if StockSaleAllocation.query.filter_by(purchase_id=purchase_id).first():
                return (
                    jsonify(
                        {
                            "error": "This purchase has recorded sales. Delete those sales before deleting the purchase."
                        }
                    ),
                    409,
                )
            db.session.delete(purchase)
            db.session.commit()
            return "", 204
    except SQLAlchemyError:
        current_app.logger.exception("Could not delete purchase")
        return jsonify({"error": "Could not delete the purchase. Please try again."}), 500
