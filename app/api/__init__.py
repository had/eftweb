from flask import Blueprint

api = Blueprint("api", __name__)

from . import (  # noqa: E402
    api_routes,
    real_estate,  # noqa: E402, F401
    stock_export,
    stock_grants,
    stock_import,
    stock_purchases,
    stock_quotes,
    stock_sales,
    stock_tax,
)
