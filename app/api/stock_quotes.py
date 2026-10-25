"""Latest available USD quotes, independent of portfolio/grant requests."""

from flask import jsonify

from app import db
from app.stocks.models import Stock
from app.stocks.ticker import ticker

from . import api


@api.route("/api/stocks/<int:stock_id>/quote", methods=["GET"])
def stock_quote(stock_id):
    stock = db.session.get(Stock, stock_id)
    if stock is None:
        return jsonify({"error": "Stock not found"}), 404
    if stock.family.is_archived:
        return jsonify({"error": "Family is archived"}), 410
    quote = ticker.get_stock_quote(stock.symbol)
    if quote["currency"] != "USD":
        quote = {
            "symbol": stock.symbol,
            "currency": "USD",
            "price": None,
            "quote_date": None,
            "fetched_at": None,
            "stale": False,
            "error": "Only USD quotes are supported.",
        }
    return jsonify(quote)
