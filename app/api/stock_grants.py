"""Stock-based grants, independent of the legacy project portfolios."""

import hashlib
import json
from datetime import date
from uuid import UUID

from flask import current_app, jsonify, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import db
from app.constants import JAVASCRIPT_MAX_SAFE_INTEGER
from app.stocks.models import GrantVesting, Stock, StockGrant, StockSaleAllocation

from . import api
from .stock_transactions import stock_write


def active_stock(stock_id):
    stock = db.session.get(Stock, stock_id)
    if stock is None:
        return None, (jsonify({"error": "Stock not found"}), 404)
    if stock.is_archived or stock.family.is_archived:
        return None, (jsonify({"error": "Stock or family is archived"}), 410)
    return stock, None


def calendar_date(value, label):
    try:
        parsed = date.fromisoformat(value) if isinstance(value, str) else None
        if parsed is None or parsed.isoformat() != value:
            raise ValueError()
    except ValueError:
        raise ValueError(f"{label} must be a valid date in YYYY-MM-DD format") from None
    return parsed


def positive_quantity(value, label):
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 < value <= JAVASCRIPT_MAX_SAFE_INTEGER
    ):
        raise ValueError(
            f"{label} must be a positive whole number of shares within the safe integer range"
        )
    return value


def grant_payload(data, stock):
    if not isinstance(data, dict):
        raise ValueError("Grant data must be an object")
    grant_date = calendar_date(data.get("grant_date"), "Grant date")
    title = data.get("title", "")
    if not isinstance(title, str) or len(title.strip()) > 256:
        raise ValueError("Grant title must be a string of at most 256 characters")
    title = title.strip() or f"{stock.symbol}-{grant_date.isoformat()}"
    quantity = positive_quantity(data.get("quantity"), "Granted quantity")
    start_date = calendar_date(data.get("vesting_start_date"), "Vesting reference date")
    schedule_type = data.get("schedule_type")
    if schedule_type not in ("quarterly", "cliff-quarterly"):
        raise ValueError("Choose a valid vesting schedule")
    customized = data.get("customized")
    if not isinstance(customized, bool):
        raise ValueError("customized must be a boolean")
    rows = data.get("vestings")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Add at least one vesting release")
    releases = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each vesting release must be an object")
        releases.append(
            {
                "date": calendar_date(row.get("date"), "Release date").isoformat(),
                "quantity": positive_quantity(row.get("quantity"), "Release quantity"),
            }
        )
    if sum(row["quantity"] for row in releases) != quantity:
        raise ValueError("Scheduled shares must exactly match the granted quantity")
    return {
        "title": title,
        "grant_date": grant_date.isoformat(),
        "quantity": quantity,
        "vesting_start_date": start_date.isoformat(),
        "schedule_type": schedule_type,
        "customized": customized,
        "vestings": sorted(releases, key=lambda row: (row["date"], row["quantity"])),
    }


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
    stock, error = active_stock(stock_id)
    if error:
        return error
    if request.method == "GET":
        return jsonify([grant.to_dict() for grant in stock.grants])
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
    rows = data.pop("vestings")
    grant = StockGrant(
        stock_id=stock.id,
        **{
            **data,
            "grant_date": date.fromisoformat(data["grant_date"]),
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
                return jsonify(
                    {
                        "error": "This grant has recorded sales. Delete those sales before deleting the grant."
                    }
                ), 409
            db.session.delete(grant)
            db.session.commit()
            return "", 204
    except SQLAlchemyError:
        current_app.logger.exception("Could not delete grant")
        return jsonify({"error": "Could not delete the grant. Please try again."}), 500
