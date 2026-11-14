from pathlib import Path

import pytest
import sqlalchemy as sa
from flask_migrate import downgrade, upgrade

from app import create_app, db
from config import TestingConfig

MIGRATIONS = str(Path(__file__).resolve().parents[1] / "migrations")
PREVIOUS = "d8f41a2c6b90"
REVISION = "e7a3b9c52f10"


def test_duplicate_ticker_migration_preserves_history_and_guards_downgrade(tmp_path, monkeypatch):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'stocks.sqlite'}"
    )
    app = create_app("testing")
    with app.app_context():
        upgrade(directory=MIGRATIONS, revision=PREVIOUS)
        with db.engine.begin() as connection:
            for sql in (
                "INSERT INTO families (id) VALUES (1)",
                "INSERT INTO stocks (id, family_id, name, symbol, is_archived) VALUES (1, 1, 'Ada', 'AAPL', 1)",
                "INSERT INTO stock_grants (id, stock_id, title, grant_number, grant_date, quantity, vesting_start_date, schedule_type, customized, creation_token, request_hash) VALUES (1, 1, 'Grant', '123', '2020-01-01', 10, '2020-01-01', 'quarterly', 1, 'grant-key', 'grant-hash')",
                "INSERT INTO grant_vestings (id, grant_id, date, quantity) VALUES (1, 1, '2021-01-01', 10)",
                "INSERT INTO stock_purchases (id, stock_id, purchase_date, quantity, plan_name, creation_token, request_hash) VALUES (1, 1, '2021-01-01', 10, 'ESPP', 'purchase-key', 'purchase-hash')",
                "INSERT INTO stock_sales (id, stock_id, transaction_date, quantity, proceeds_per_share, currency, creation_token, request_hash) VALUES (1, 1, '2022-01-01', 4, 100, 'USD', 'sale-key', 'sale-hash')",
                "INSERT INTO stock_sale_allocations (sale_id, vesting_id, quantity) VALUES (1, 1, 2)",
                "INSERT INTO stock_sale_allocations (sale_id, purchase_id, quantity) VALUES (1, 1, 2)",
                "INSERT INTO stock_import_receipts (stock_id, creation_token, request_hash, result) VALUES (1, 'import-key', 'import-hash', '{}')",
            ):
                connection.execute(sa.text(sql))
            tables = (
                "stocks",
                "stock_grants",
                "grant_vestings",
                "stock_purchases",
                "stock_sales",
                "stock_sale_allocations",
                "stock_import_receipts",
            )
            before = {
                table: connection.execute(sa.text(f"SELECT * FROM {table}")).all()
                for table in tables
            }

        upgrade(directory=MIGRATIONS, revision=REVISION)
        assert sa.inspect(db.engine).get_unique_constraints("stocks") == []
        with db.engine.begin() as connection:
            for table, rows in before.items():
                assert connection.execute(sa.text(f"SELECT * FROM {table}")).all() == rows
            assert (
                "AUTOINCREMENT"
                in connection.execute(
                    sa.text("SELECT sql FROM sqlite_master WHERE name='stocks'")
                ).scalar_one()
            )
            assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
            connection.execute(
                sa.text(
                    "INSERT INTO stocks (id, family_id, name, symbol) VALUES (2, 1, 'Partner', 'AAPL')"
                )
            )

        with pytest.raises(SystemExit) as blocked:
            downgrade(directory=MIGRATIONS, revision=PREVIOUS)
        assert blocked.value.code == 1
        with db.engine.begin() as connection:
            assert connection.execute(sa.text("SELECT COUNT(*) FROM stocks")).scalar_one() == 2
            assert (
                connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
                == REVISION
            )
            connection.execute(sa.text("DELETE FROM stocks WHERE id=2"))
            connection.execute(
                sa.text("INSERT INTO stocks (family_id, name, symbol) VALUES (1, 'Other', 'MSFT')")
            )
            assert connection.execute(sa.text("SELECT MAX(id) FROM stocks")).scalar_one() == 3

        downgrade(directory=MIGRATIONS, revision=PREVIOUS)
        assert sa.inspect(db.engine).get_unique_constraints("stocks") == [
            {"name": "uq_stock_family_symbol", "column_names": ["family_id", "symbol"]}
        ]
        upgrade(directory=MIGRATIONS, revision=REVISION)
        client = app.test_client()
        assert client.post("/api/stocks/1/restore").status_code == 200
        assert client.get("/api/stocks/1/grants").get_json()[0]["grant_number"] == "123"
        assert client.get("/api/stocks/1/purchases").get_json()[0]["quantity"] == 10
        assert client.get("/api/stocks/1/sales").get_json()[0]["allocations"] == [
            {"purchase_id": 1, "quantity": 2},
            {"vesting_id": 1, "quantity": 2},
        ]
        assert client.delete("/api/stocks/1").status_code == 200
        # Check cleanup without relying on SQLite's optional ON DELETE cascades.
        assert client.delete("/api/stocks/1?permanent=true").status_code == 204
        with db.engine.connect() as connection:
            for table in tables[1:]:
                assert (
                    connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one() == 0
                )
            assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        db.session.remove()
        db.engine.dispose()
