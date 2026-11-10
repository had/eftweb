import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from flask_migrate import downgrade, upgrade

from app import create_app, db
from config import TestingConfig

MIGRATIONS = str(Path(__file__).resolve().parents[1] / "migrations")
PREVIOUS = "b9e4c27a810f"
REVISION = "c2e6a8f41d90"


def test_purchases_migration_preserves_rsu_sales_retries_and_can_be_reapplied(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'migration.sqlite'}"
    )
    app = create_app("testing")
    data = {
        "transaction_date": "2022-01-01",
        "quantity": 5,
        "proceeds_per_share": "100",
        "allocations": [{"vesting_id": 1, "quantity": 5}],
    }
    token = str(uuid4())
    request_hash = hashlib.sha256(
        json.dumps(
            {**data, "proceeds_per_share": "100.000000", "currency": "USD"}, sort_keys=True
        ).encode()
    ).hexdigest()
    with app.app_context():
        upgrade(directory=MIGRATIONS, revision=PREVIOUS)
        with db.engine.begin() as connection:
            for sql in (
                "INSERT INTO families (id) VALUES (1)",
                "INSERT INTO stocks (id, family_id, name, symbol, is_archived) VALUES (1, 1, 'Apple', 'AAPL', 0)",
                "INSERT INTO stock_grants (id, stock_id, title, grant_date, quantity, vesting_start_date, schedule_type, customized, creation_token, request_hash) VALUES (1, 1, 'Grant', '2020-01-01', 100, '2020-01-01', 'quarterly', 0, 'grant-token', 'hash')",
                "INSERT INTO grant_vestings (id, grant_id, date, quantity) VALUES (1, 1, '2021-01-01', 100)",
                "INSERT INTO projects (id, name) VALUES (1, 'Legacy')",
                "INSERT INTO sale_events (id, project_id, quantity) VALUES (1, 1, 12)",
            ):
                connection.execute(sa.text(sql))
            connection.execute(
                sa.text(
                    "INSERT INTO stock_sales (id, stock_id, transaction_date, quantity, proceeds_per_share, currency, creation_token, request_hash) VALUES (1, 1, '2022-01-01', 5, 100, 'USD', :token, :hash)"
                ),
                {"token": token, "hash": request_hash},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO stock_sale_allocations (id, sale_id, vesting_id, quantity) VALUES (7, 1, 1, 5)"
                )
            )
        upgrade(directory=MIGRATIONS, revision=REVISION)
        # Exercise current ORM/API code only after applying its current schema.
        upgrade(directory=MIGRATIONS, revision="head")
        client = app.test_client()
        replay = client.post("/api/stocks/1/sales", json=data, headers={"Idempotency-Key": token})
        assert replay.status_code == 200
        assert replay.get_json()["allocations"] == data["allocations"]
        with db.engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT id, vesting_id, purchase_id, quantity FROM stock_sale_allocations")
            ).one() == (7, 1, None, 5)
            assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        purchase = client.post(
            "/api/stocks/1/purchases",
            json={"purchase_date": "2022-01-01", "quantity": 10},
            headers={"Idempotency-Key": str(uuid4())},
        ).get_json()
        sale = client.post(
            "/api/stocks/1/sales",
            json={**data, "allocations": [{"purchase_id": purchase["id"], "quantity": 5}]},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert sale.status_code == 201
        db.session.remove()
        downgrade(directory=MIGRATIONS, revision=REVISION)
        with pytest.raises(SystemExit) as blocked:
            downgrade(directory=MIGRATIONS, revision=PREVIOUS)
        assert blocked.value.code == 1
        upgrade(directory=MIGRATIONS, revision="head")
        assert client.delete(f"/api/stocks/1/sales/{sale.get_json()['id']}").status_code == 204
        db.session.remove()
        downgrade(directory=MIGRATIONS, revision=PREVIOUS)
        assert "stock_purchases" not in sa.inspect(db.engine).get_table_names()
        with db.engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT id, vesting_id, quantity FROM stock_sale_allocations")
            ).one() == (7, 1, 5)
            assert (
                connection.execute(sa.text("SELECT quantity FROM sale_events")).scalar_one() == 12
            )
            assert (
                connection.execute(sa.text("SELECT quantity FROM stock_grants")).scalar_one() == 100
            )
        upgrade(directory=MIGRATIONS, revision=REVISION)
        upgrade(directory=MIGRATIONS, revision="head")
        assert client.get("/api/stocks/1/purchases").get_json() == []
        assert (
            client.post(
                "/api/stocks/1/sales", json=data, headers={"Idempotency-Key": token}
            ).status_code
            == 200
        )
        db.session.remove()
        db.engine.dispose()
