"""Download a stock and all of its acquisition and sale records."""

from flask import current_app, jsonify, send_file
from sqlalchemy import text
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename

from app import db
from app.stocks.models import Stock
from app.stocks.xlsx_export import build_stock_export

from . import api

XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@api.route("/api/stocks/<int:stock_id>/export", methods=["GET"])
def export_stock(stock_id):
    try:
        # A separate session avoids cached ORM state. SERIALIZABLE keeps all lazy
        # relationship reads in one snapshot on supported database backends.
        with (
            db.engine.connect().execution_options(isolation_level="SERIALIZABLE") as connection,
            Session(bind=connection) as session,
        ):
            if connection.dialect.name == "sqlite":
                # sqlite3's legacy transaction mode does not BEGIN for SELECTs.
                session.execute(text("BEGIN"))
            stock = session.get(Stock, stock_id)
            if stock is None:
                return jsonify({"error": "Stock not found"}), 404
            if stock.is_archived or stock.family.is_archived:
                return jsonify({"error": "Stock or family is archived"}), 410
            snapshot = {
                "name": stock.name,
                "symbol": stock.symbol,
                "grants": [grant.to_dict() for grant in stock.grants],
                "purchases": [purchase.to_dict() for purchase in stock.purchases],
                "sales": [sale.to_dict() for sale in stock.sales],
            }
        # Release the read transaction before formatting and serving the workbook.
        output = build_stock_export(snapshot)
        symbol = secure_filename(snapshot["symbol"]) or "stock"
        response = send_file(
            output,
            mimetype=XLSX_MIME_TYPE,
            as_attachment=True,
            download_name=f"{symbol}-export.xlsx",
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception:
        current_app.logger.exception("Could not export stock %s", stock_id)
        return jsonify({"error": "Could not export the stock. Please try again."}), 500
