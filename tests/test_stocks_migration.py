from pathlib import Path

import sqlalchemy as sa
from flask_migrate import downgrade, upgrade

from app import create_app, db
from config import TestingConfig

MIGRATIONS = str(Path(__file__).resolve().parents[1] / "migrations")
PREVIOUS_REVISION = "7ab43e902d16"
STOCKS_REVISION = "6d2f8a9c1e40"


def test_family_stock_migration_upgrades_and_downgrades(tmp_path, monkeypatch):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'stocks.sqlite'}"
    )
    app = create_app("testing")
    with app.app_context():
        upgrade(directory=MIGRATIONS, revision=PREVIOUS_REVISION)
        with db.engine.begin() as connection:
            connection.execute(sa.text("INSERT INTO families (id) VALUES (1)"))
        upgrade(directory=MIGRATIONS, revision=STOCKS_REVISION)
        inspector = sa.inspect(db.engine)
        assert inspector.get_unique_constraints("stocks") == [
            {"name": "uq_stock_family_symbol", "column_names": ["family_id", "symbol"]}
        ]
        assert inspector.get_foreign_keys("stocks")[0]["referred_table"] == "families"
        with db.engine.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO stocks (family_id, name, symbol) VALUES (1, 'Apple', 'AAPL')"
            ))
            assert connection.execute(sa.text("SELECT is_archived FROM stocks")).scalar_one() == 0
        downgrade(directory=MIGRATIONS, revision=PREVIOUS_REVISION)
        assert "stocks" not in sa.inspect(db.engine).get_table_names()
        with db.engine.connect() as connection:
            assert connection.execute(sa.text("SELECT id FROM families")).scalar_one() == 1
        upgrade(directory=MIGRATIONS, revision=STOCKS_REVISION)
        assert "stocks" in sa.inspect(db.engine).get_table_names()
        db.session.remove()
        db.engine.dispose()
