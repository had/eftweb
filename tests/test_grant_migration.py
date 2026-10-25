from pathlib import Path

import sqlalchemy as sa
from flask_migrate import downgrade, upgrade

from app import create_app, db
from config import TestingConfig

MIGRATIONS = str(Path(__file__).resolve().parents[1] / "migrations")


def test_grant_migration_preserves_stock_and_legacy_data(tmp_path, monkeypatch):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'grants.sqlite'}"
    )
    app = create_app("testing")
    with app.app_context():
        upgrade(directory=MIGRATIONS, revision="6d2f8a9c1e40")
        with db.engine.begin() as connection:
            for sql in (
                "INSERT INTO families (id) VALUES (1)",
                "INSERT INTO stocks (id, family_id, name, symbol) VALUES (1, 1, 'Apple', 'AAPL')",
                "INSERT INTO projects (id, name) VALUES (1, 'Legacy')",
                "INSERT INTO rsu_plans (id, project_id, name, symbol) VALUES (1, 1, 'Legacy grant', 'AAPL')",
                "INSERT INTO rsu_stocks (id, rsu_plan_id, count) VALUES (1, 1, 123)",
            ):
                connection.execute(sa.text(sql))
        upgrade(directory=MIGRATIONS, revision="ab4e91d6c280")
        inspector = sa.inspect(db.engine)
        assert inspector.get_foreign_keys("stock_grants")[0]["referred_table"] == "stocks"
        assert inspector.get_foreign_keys("grant_vestings")[0]["options"]["ondelete"] == "CASCADE"
        assert inspector.get_unique_constraints("stock_grants")[0]["column_names"] == [
            "stock_id",
            "creation_token",
        ]
        with db.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO stock_grants (stock_id, title, grant_date, quantity, vesting_start_date, schedule_type, customized, creation_token, request_hash) "
                    "VALUES (1, 'New grant', '2026-01-01', 100, '2026-01-01', 'quarterly', 1, 'test-token', 'hash')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO grant_vestings (grant_id, date, quantity) VALUES (1, '2030-01-01', 100)"
                )
            )
        downgrade(directory=MIGRATIONS, revision="6d2f8a9c1e40")
        assert {"stock_grants", "grant_vestings"}.isdisjoint(
            sa.inspect(db.engine).get_table_names()
        )
        with db.engine.connect() as connection:
            assert (
                connection.execute(sa.text("SELECT name FROM stocks WHERE id = 1")).scalar_one()
                == "Apple"
            )
            assert (
                connection.execute(sa.text("SELECT name FROM rsu_plans WHERE id = 1")).scalar_one()
                == "Legacy grant"
            )
            assert (
                connection.execute(
                    sa.text("SELECT count FROM rsu_stocks WHERE id = 1")
                ).scalar_one()
                == 123
            )
        upgrade(directory=MIGRATIONS, revision="ab4e91d6c280")
        assert {"stock_grants", "grant_vestings"}.issubset(sa.inspect(db.engine).get_table_names())
        db.session.remove()
        db.engine.dispose()
