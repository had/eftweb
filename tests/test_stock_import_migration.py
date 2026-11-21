from pathlib import Path

import sqlalchemy as sa
from flask_migrate import downgrade, upgrade

from app import create_app, db
from config import TestingConfig

MIGRATIONS = str(Path(__file__).resolve().parents[1] / "migrations")
PREVIOUS = "c2e6a8f41d90"
REVISION = "d8f41a2c6b90"


def test_import_migration_preserves_records_constraints_and_reapplies(tmp_path, monkeypatch):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'migration.sqlite'}"
    )
    app = create_app("testing")
    with app.app_context():
        upgrade(directory=MIGRATIONS, revision=PREVIOUS)
        with db.engine.begin() as connection:
            for sql in (
                "INSERT INTO families (id) VALUES (1)",
                "INSERT INTO stocks (id, family_id, name, symbol, is_archived) VALUES (1, 1, 'Apple', 'AAPL', 0)",
                "INSERT INTO stock_grants (id, stock_id, title, grant_date, quantity, vesting_start_date, schedule_type, customized, creation_token, request_hash) VALUES (1, 1, 'Grant', '2020-01-01', 10, '2020-01-01', 'quarterly', 1, 'grant-key', 'grant-hash')",
                "INSERT INTO grant_vestings (id, grant_id, date, quantity) VALUES (1, 1, '2021-01-01', 10)",
                "INSERT INTO stock_sales (id, stock_id, transaction_date, quantity, proceeds_per_share, currency, creation_token, request_hash) VALUES (1, 1, '2022-01-01', 2, 100, 'USD', 'sale-key', 'sale-hash')",
                "INSERT INTO stock_sale_allocations (sale_id, vesting_id, quantity) VALUES (1, 1, 2)",
            ):
                connection.execute(sa.text(sql))
        upgrade(directory=MIGRATIONS, revision=REVISION)
        with db.engine.begin() as connection:
            for table in ("stock_grants", "stock_sales"):
                assert (
                    "AUTOINCREMENT"
                    in connection.execute(
                        sa.text("SELECT sql FROM sqlite_master WHERE name=:name"), {"name": table}
                    ).scalar_one()
                )
            assert connection.execute(
                sa.text("SELECT quantity, grant_number, request_hash FROM stock_grants")
            ).one() == (10, None, "grant-hash")
            assert connection.execute(
                sa.text(
                    "SELECT quantity, import_source, source_order_number, source_fingerprint, request_hash FROM stock_sales"
                )
            ).one() == (2, None, None, None, "sale-hash")
            assert connection.execute(
                sa.text("SELECT vesting_id, quantity FROM stock_sale_allocations")
            ).one() == (1, 2)
            connection.execute(sa.text("UPDATE stock_grants SET grant_number='000123' WHERE id=1"))
            assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        assert any(
            constraint["name"] == "uq_stock_grant_number"
            for constraint in sa.inspect(db.engine).get_unique_constraints("stock_grants")
        )
        assert any(
            constraint["name"] == "uq_stock_sale_source_group"
            for constraint in sa.inspect(db.engine).get_unique_constraints("stock_sales")
        )
        db.session.remove()
        downgrade(directory=MIGRATIONS, revision=PREVIOUS)
        assert "stock_import_receipts" not in sa.inspect(db.engine).get_table_names()
        with db.engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT quantity, request_hash FROM stock_grants")
            ).one() == (10, "grant-hash")
            assert connection.execute(
                sa.text("SELECT quantity, request_hash FROM stock_sales")
            ).one() == (2, "sale-hash")
        upgrade(directory=MIGRATIONS, revision=REVISION)
        upgrade(directory=MIGRATIONS, revision="head")
        assert app.test_client().get("/api/stocks/1/grants").get_json()[0]["grant_number"] is None
        assert app.test_client().get("/api/stocks/1/sales").get_json()[0]["allocations"] == [
            {"vesting_id": 1, "quantity": 2}
        ]
        db.session.remove()
        db.engine.dispose()
