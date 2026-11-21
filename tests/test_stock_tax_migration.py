from pathlib import Path

import sqlalchemy as sa
from flask_migrate import downgrade, upgrade

from app import create_app, db
from config import TestingConfig

MIGRATIONS = str(Path(__file__).resolve().parents[1] / "migrations")
PREVIOUS = "d8f41a2c6b90"
REVISION = "ef2a91c7d430"


def test_stock_tax_migration_initializes_money_and_preserves_unknown_metadata(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'migration.sqlite'}"
    )
    app = create_app("testing")
    with app.app_context():
        upgrade(directory=MIGRATIONS, revision=PREVIOUS)
        with db.engine.begin() as connection:
            for sql in (
                "INSERT INTO families (id) VALUES (1)",
                "INSERT INTO stocks (id, family_id, name, symbol, is_archived) VALUES (1, 1, 'Example', 'EXM', 0)",
                "INSERT INTO stock_grants (id, stock_id, title, grant_date, quantity, vesting_start_date, schedule_type, customized, creation_token, request_hash) VALUES (1, 1, 'Grant', '2020-01-01', 10, '2020-01-01', 'quarterly', 1, 'grant-key', 'grant-hash')",
                "INSERT INTO grant_vestings (id, grant_id, date, quantity) VALUES (1, 1, '2021-01-01', 10)",
                "INSERT INTO stock_purchases (id, stock_id, plan_name, purchase_date, quantity, creation_token, request_hash) VALUES (1, 1, 'ESPP', '2021-01-01', 10, 'purchase-key', 'purchase-hash')",
                "INSERT INTO stock_sales (id, stock_id, transaction_date, quantity, proceeds_per_share, currency, creation_token, request_hash) VALUES (1, 1, '2022-01-01', 2, 100, 'USD', 'sale-key', 'sale-hash')",
                "INSERT INTO stock_sale_allocations (sale_id, vesting_id, quantity) VALUES (1, 1, 2)",
            ):
                connection.execute(sa.text(sql))
        upgrade(directory=MIGRATIONS, revision=REVISION)
        with db.engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT approval_date, taxpayer_role FROM stock_grants")
            ).one() == (None, None)
            for table, column in (
                ("grant_vestings", "acquisition_fmv"),
                ("stock_purchases", "acquisition_fmv"),
                ("stock_sales", "fees"),
            ):
                assert (
                    connection.execute(sa.text(f"SELECT {column} FROM {table}")).scalar_one() == 0
                )
            assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        tables = sa.inspect(db.engine).get_table_names()
        assert {
            "capital_gain_statements",
            "capital_gain_helper_lines",
            "stock_tax_receipts",
            "usd_eur_rates",
            "fx_coverage",
        } <= set(tables)
        db.session.remove()
        downgrade(directory=MIGRATIONS, revision=PREVIOUS)
        with db.engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT quantity, request_hash FROM stock_sales")
            ).one() == (2, "sale-hash")
        upgrade(directory=MIGRATIONS, revision=REVISION)
        assert app.test_client().get("/api/stocks/1/grants").get_json()[0]["taxpayer_role"] is None
        db.session.remove()
        db.engine.dispose()
