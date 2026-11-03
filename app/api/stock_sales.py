"""Persist sales and explicit acquisition-lot allocations, without tax computation."""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID
from zoneinfo import ZoneInfo

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

from . import api
from .stock_grants import active_stock, calendar_date, positive_quantity
from .stock_transactions import stock_write


def sale_payload(data):
    if not isinstance(data, dict):
        raise ValueError("Sale data must be an object")
    transaction_date = calendar_date(data.get("transaction_date"), "Transaction date")
    if transaction_date > datetime.now(ZoneInfo("Europe/Paris")).date():
        raise ValueError("Transaction date cannot be in the future")
    quantity = positive_quantity(data.get("quantity"), "Sale quantity")
    value = data.get("proceeds_per_share")
    try:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise InvalidOperation()
        price = Decimal(str(value))
        if not price.is_finite() or not 0 < price < 100_000_000:
            raise InvalidOperation()
        if price != price.quantize(Decimal("0.000001")):
            raise InvalidOperation()
    except InvalidOperation:
        raise ValueError(
            "Proceeds per share must be positive, below 100,000,000 USD, with at most six decimals"
        ) from None
    if data.get("currency", "USD") != "USD":
        raise ValueError("Only USD sales are supported")
    rows = data.get("allocations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Allocate shares to at least one acquisition lot")
    allocations = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each allocation must be an object")
        sources = [key for key in ("vesting_id", "purchase_id") if key in row]
        if len(sources) != 1:
            raise ValueError("Each allocation must identify exactly one vesting or purchase")
        source = sources[0]
        source_id = positive_quantity(row[source], "Acquisition ID")
        key = (source, source_id)
        if key in seen:
            raise ValueError("Each acquisition lot can appear only once")
        seen.add(key)
        allocations.append(
            {
                source: source_id,
                "quantity": positive_quantity(row.get("quantity"), "Allocated quantity"),
            }
        )
    if sum(row["quantity"] for row in allocations) != quantity:
        raise ValueError("Allocated shares must exactly match the sale quantity")
    return {
        "transaction_date": transaction_date.isoformat(),
        "quantity": quantity,
        "proceeds_per_share": format(price, ".6f"),
        "currency": "USD",
        # Preserve legacy RSU canonicalization so existing retry hashes remain valid.
        "allocations": sorted(
            allocations,
            key=lambda row: ("purchase_id" in row, row.get("vesting_id", row.get("purchase_id"))),
        ),
    }


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
            for row in data["allocations"]:
                source = "vesting_id" if "vesting_id" in row else "purchase_id"
                key = (source, row[source])
                pocket = pockets.get(key)
                if pocket is None:
                    return jsonify({"error": "Acquisition lot not found for this stock"}), 400
                acquired_date, quantity = pocket
                if acquired_date.isoformat() > data["transaction_date"]:
                    return (
                        jsonify(
                            {"error": "Shares must have been acquired by the transaction date"}
                        ),
                        400,
                    )
                if row["quantity"] > quantity - used.get(key, 0):
                    return (
                        jsonify(
                            {
                                "error": "An acquisition lot no longer has enough available shares. Reload to review its balance."
                            }
                        ),
                        409,
                    )
            allocations = data.pop("allocations")
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
