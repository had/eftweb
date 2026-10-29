from pathlib import Path

import sqlalchemy as sa
from flask_migrate import downgrade, upgrade

from app import create_app, db
from config import TestingConfig

MIGRATIONS = str(Path(__file__).resolve().parents[1] / "migrations")


def test_sales_migration_preserves_existing_data_and_can_be_reapplied(tmp_path, monkeypatch):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'migration.sqlite'}"
    )
    app = create_app("testing")
    with app.app_context():
        upgrade(directory=MIGRATIONS, revision="ab4e91d6c280")
        with db.engine.begin() as connection:
            for sql in (
                "INSERT INTO families (id) VALUES (1)",
                "INSERT INTO stocks (id, family_id, name, symbol, is_archived) VALUES (1, 1, 'Apple', 'AAPL', 0)",
                "INSERT INTO stock_grants (id, stock_id, title, grant_date, quantity, vesting_start_date, schedule_type, customized, creation_token, request_hash) VALUES (1, 1, 'Grant', '2020-01-01', 100, '2020-01-01', 'quarterly', 0, 'token', 'hash')",
                "INSERT INTO grant_vestings (id, grant_id, date, quantity) VALUES (1, 1, '2021-01-01', 100)",
                "INSERT INTO projects (id, name) VALUES (1, 'Legacy')",
                "INSERT INTO sale_events (id, project_id, quantity) VALUES (1, 1, 12)",
            ):
                connection.execute(sa.text(sql))
        upgrade(directory=MIGRATIONS, revision="b9e4c27a810f")
        inspector = sa.inspect(db.engine)
        assert inspector.get_unique_constraints("stock_sales")[0]["column_names"] == [
            "stock_id",
            "creation_token",
        ]
        assert {
            fk["referred_table"] for fk in inspector.get_foreign_keys("stock_sale_allocations")
        } == {"stock_sales", "grant_vestings"}
        with db.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO stock_sales (id, stock_id, transaction_date, quantity, proceeds_per_share, currency, creation_token, request_hash) VALUES (1, 1, '2022-01-01', 5, 123.456789, 'USD', 'sale-token', 'hash')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO stock_sale_allocations (sale_id, vesting_id, quantity) VALUES (1, 1, 5)"
                )
            )
        downgrade(directory=MIGRATIONS, revision="ab4e91d6c280")
        assert {"stock_sales", "stock_sale_allocations"}.isdisjoint(
            sa.inspect(db.engine).get_table_names()
        )
        with db.engine.connect() as connection:
            for table, field, expected in (
                ("stocks", "name", "Apple"),
                ("stock_grants", "quantity", 100),
                ("grant_vestings", "quantity", 100),
                ("sale_events", "quantity", 12),
            ):
                assert (
                    connection.execute(
                        sa.text(f"SELECT {field} FROM {table} WHERE id = 1")
                    ).scalar_one()
                    == expected
                )
        upgrade(directory=MIGRATIONS, revision="b9e4c27a810f")
        assert {"stock_sales", "stock_sale_allocations"}.issubset(
            sa.inspect(db.engine).get_table_names()
        )
        db.session.remove()
        db.engine.dispose()
