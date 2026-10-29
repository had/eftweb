"""Serialize stock mutations before reading pocket availability."""

from contextlib import contextmanager

from sqlalchemy import text

from app import db
from app.stocks.models import Stock


@contextmanager
def stock_write(stock_id):
    try:
        if db.engine.dialect.name == "sqlite":
            # SQLite ignores FOR UPDATE. Reserve the write transaction before any reads.
            db.session.execute(text("BEGIN IMMEDIATE"))
        else:
            db.session.query(Stock).filter_by(id=stock_id).with_for_update().first()
        yield
    finally:
        # Also release locks on validation errors and replayed requests.
        db.session.rollback()
