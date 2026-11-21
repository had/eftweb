"""Persist sales and explicit acquisition-lot allocations, without tax computation."""

import hashlib
import json
from datetime import date
from decimal import Decimal
from uuid import UUID

from flask import current_app, jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.stocks.models import (
    GrantVesting,
    StockGrant,
    StockPurchase,
    StockSale,
    StockSaleAllocation,
)
from app.stocks.tax_inputs import apply_fmv
from app.stocks.validation import allocation_error, sale_payload

from . import api
from .stock_grants import active_stock
from .stock_transactions import stock_write


@api.route("/api/stocks/<int:stock_id>/sales", methods=["GET", "POST"])
def stock_sales(stock_id):
    if request.method == "GET":
        stock, error = active_stock(stock_id)
        if error:
            return error
        return jsonify([sale.to_dict() for sale in stock.sales])
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
                data = sale_payload(request.get_json(silent=True))
            except ValueError as validation_error:
                return jsonify({"error": str(validation_error)}), 400
            request_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
            existing = StockSale.query.filter_by(stock_id=stock_id, creation_token=token).first()
            if existing:
                if existing.request_hash != request_hash:
                    return (
                        jsonify(
                            {
                                "error": "This creation token was already used for different sale data. Reload to review the saved sale."
                            }
                        ),
                        409,
                    )
                return jsonify(existing.to_dict()), 200

            vesting_ids = [row["vesting_id"] for row in data["allocations"] if "vesting_id" in row]
            purchase_ids = [
                row["purchase_id"] for row in data["allocations"] if "purchase_id" in row
            ]
            pockets = {
                ("vesting_id", pocket.id): (pocket.date, pocket.quantity)
                for pocket in GrantVesting.query.join(StockGrant)
                .filter(
                    StockGrant.stock_id == stock_id,
                    GrantVesting.id.in_(vesting_ids),
                )
                .all()
            }
            pockets.update(
                {
                    ("purchase_id", purchase.id): (purchase.purchase_date, purchase.quantity)
                    for purchase in StockPurchase.query.filter(
                        StockPurchase.stock_id == stock_id, StockPurchase.id.in_(purchase_ids)
                    ).all()
                }
            )
            used = {}
            for source, ids in (("vesting_id", vesting_ids), ("purchase_id", purchase_ids)):
                column = getattr(StockSaleAllocation, source)
                used.update(
                    {
                        (source, source_id): quantity
                        for source_id, quantity in db.session.query(
                            column, func.sum(StockSaleAllocation.quantity)
                        )
                        .filter(column.in_(ids))
                        .group_by(column)
                        .all()
                    }
                )
            error = allocation_error(data, pockets, used)
            if error:
                message, status = error
                return jsonify({"error": message}), status
            allocations = data.pop("allocations")
            try:
                apply_fmv(stock_id, allocations)
            except ValueError as validation_error:
                return jsonify({"error": str(validation_error)}), 400
            sale = StockSale(
                stock_id=stock_id,
                **{
                    **data,
                    "transaction_date": date.fromisoformat(data["transaction_date"]),
                    "proceeds_per_share": Decimal(data["proceeds_per_share"]),
                },
                creation_token=token,
                request_hash=request_hash,
                allocations=[StockSaleAllocation(**row) for row in allocations],
            )
            db.session.add(sale)
            db.session.commit()
            return jsonify(sale.to_dict()), 201
    except SQLAlchemyError:
        current_app.logger.exception("Could not save sale")
        return jsonify({"error": "Could not save the sale. Please try again."}), 500


@api.route("/api/stocks/<int:stock_id>/sales/<int:sale_id>", methods=["DELETE"])
def delete_stock_sale(stock_id, sale_id):
    try:
        with stock_write(stock_id):
            _, error = active_stock(stock_id)
            if error:
                return error
            sale = StockSale.query.filter_by(id=sale_id, stock_id=stock_id).first()
            if sale is None:
                return jsonify({"error": "Sale not found for this stock"}), 404
            db.session.delete(sale)
            db.session.commit()
            return "", 204
    except SQLAlchemyError:
        current_app.logger.exception("Could not delete sale")
        return jsonify({"error": "Could not delete the sale. Please try again."}), 500


@api.route("/api/stocks/<int:stock_id>/sales", methods=["DELETE"])
def delete_all_stock_sales(stock_id):
    try:
        with stock_write(stock_id):
            _, error = active_stock(stock_id)
            if error:
                return error
            for sale in StockSale.query.filter_by(stock_id=stock_id).all():
                db.session.delete(sale)
            db.session.commit()
            return "", 204
    except SQLAlchemyError:
        current_app.logger.exception("Could not delete all stock sales")
        return jsonify({"error": "Could not delete all sales. Please try again."}), 500
