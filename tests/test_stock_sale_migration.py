from pathlib import Path

import sqlalchemy as sa
from flask_migrate import downgrade, upgrade

from app import create_app, db
from config import TestingConfig

MIGRATIONS = str(Path(__file__).resolve().parents[1] / "migrations")
PREVIOUS_REVISION = "f7b2d6e84c16"
CLEANUP_REVISION = "7ab43e902d16"
OBSOLETE_TABLES = ("direct_stocks_sales", "rsu_sales")


def table_schema(inspector, table_name):
    return (
        [
            (column["name"], str(column["type"]), column["nullable"])
            for column in inspector.get_columns(table_name)
        ],
        inspector.get_pk_constraint(table_name),
        inspector.get_foreign_keys(table_name),
    )


def test_stock_sale_cleanup_drops_old_data_and_preserves_current_sales(tmp_path, monkeypatch):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'migration.sqlite'}"
    )
    app = create_app("testing")
    with app.app_context():
        upgrade(directory=MIGRATIONS, revision=PREVIOUS_REVISION)
        inspector = sa.inspect(db.engine)
        original_schemas = {table: table_schema(inspector, table) for table in OBSOLETE_TABLES}
        with db.engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO projects (id, name) VALUES (1, 'Migration test')")
            )
            connection.execute(
                sa.text(
                    "INSERT INTO sale_events (id, project_id, type, symbol, quantity) "
                    "VALUES (1, 1, 'RSU', 'TEST', 3)"
                )
            )
            for table in OBSOLETE_TABLES:
                connection.execute(
                    sa.text(f"INSERT INTO {table} (id, project_id, quantity) VALUES (1, 1, 2)")
                )

        upgrade(directory=MIGRATIONS, revision=CLEANUP_REVISION)
        assert set(OBSOLETE_TABLES).isdisjoint(sa.inspect(db.engine).get_table_names())
        with db.engine.connect() as connection:
            assert (
                connection.execute(
                    sa.text("SELECT quantity FROM sale_events WHERE id = 1")
                ).scalar_one()
                == 3
            )
            assert (
                connection.execute(sa.text("SELECT name FROM projects WHERE id = 1")).scalar_one()
                == "Migration test"
            )

        downgrade(directory=MIGRATIONS, revision=PREVIOUS_REVISION)
        inspector = sa.inspect(db.engine)
        with db.engine.connect() as connection:
            for table in OBSOLETE_TABLES:
                assert table_schema(inspector, table) == original_schemas[table]
                assert (
                    connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one() == 0
                )

        upgrade(directory=MIGRATIONS, revision=CLEANUP_REVISION)
        assert set(OBSOLETE_TABLES).isdisjoint(sa.inspect(db.engine).get_table_names())
        db.session.remove()
        db.engine.dispose()
