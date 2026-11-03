from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from threading import Barrier
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import create_app, db
from app.constants import JAVASCRIPT_MAX_SAFE_INTEGER
from config import TestingConfig


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'purchases.sqlite'}"
    )
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def stock(app):
    from app.family.models import Family
    from app.stocks.models import GrantVesting, Stock, StockGrant

    stock = Stock(family=Family(), name="Apple", symbol="AAPL")
    stock.grants = [
        StockGrant(
            title="RSU grant",
            grant_date=date(2020, 1, 1),
            quantity=100,
            vesting_start_date=date(2020, 1, 1),
            schedule_type="quarterly",
            customized=False,
            creation_token=str(uuid4()),
            request_hash="hash",
            vestings=[GrantVesting(date=date(2021, 1, 1), quantity=100)],
        )
    ]
    db.session.add(stock)
    db.session.commit()
    return stock


def purchase(client, stock_id, data=None, token=None):
    return client.post(
        f"/api/stocks/{stock_id}/purchases",
        json=(
            data
            if data is not None
            else {
                "purchase_date": "2022-06-01",
                "quantity": 20,
            }
        ),
        headers={"Idempotency-Key": token or str(uuid4())},
    )


def sell(client, stock_id, allocations, transaction_date="2023-01-01", token=None):
    return client.post(
        f"/api/stocks/{stock_id}/sales",
        json={
            "transaction_date": transaction_date,
            "quantity": sum(row["quantity"] for row in allocations),
            "proceeds_per_share": "123.456789",
            "allocations": allocations,
        },
        headers={"Idempotency-Key": token or str(uuid4())},
    )


def test_purchase_roundtrip_retry_generic_plan_and_delete(app, stock):
    client = app.test_client()
    stock_id = stock.id
    key = str(uuid4())
    endpoint = f"/api/stocks/{stock_id}/purchases"
    assert client.get(endpoint).get_json() == []
    response = purchase(client, stock_id, token=key)
    assert response.status_code == 201
    saved = response.get_json()
    assert saved == {
        "id": saved["id"],
        "stock_id": stock_id,
        "purchase_date": "2022-06-01",
        "quantity": 20,
        "plan_name": "ESPP",
    }
    assert purchase(client, stock_id, token=key).get_json() == saved
    assert (
        purchase(client, stock_id, {"purchase_date": "2022-06-01", "quantity": 21}, key).status_code
        == 409
    )
    assert (
        purchase(
            client,
            stock_id,
            {"purchase_date": "2021-01-01", "quantity": 10, "plan_name": " Other purchase "},
        ).status_code
        == 201
    )
    db.session.remove()
    assert [row["plan_name"] for row in client.get(endpoint).get_json()] == [
        "Other purchase",
        "ESPP",
    ]
    assert client.delete(f"{endpoint}/{saved['id']}").status_code == 204
    assert client.delete(f"{endpoint}/{saved['id']}").status_code == 404
    assert len(client.get(endpoint).get_json()) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"purchase_date": "2025-02-29"},
        {"purchase_date": "9999-01-01"},
        {"purchase_date": None},
        {"quantity": 0},
        {"quantity": -1},
        {"quantity": 1.5},
        {"quantity": True},
        {"quantity": "20"},
        {"quantity": JAVASCRIPT_MAX_SAFE_INTEGER + 1},
        {"plan_name": ""},
        {"plan_name": None},
        {"plan_name": "a" * 257},
    ],
)
def test_invalid_purchase_data(app, stock, changes):
    assert (
        purchase(
            app.test_client(), stock.id, {"purchase_date": "2022-06-01", "quantity": 20, **changes}
        ).status_code
        == 400
    )


def test_today_safe_integer_and_required_token(app, stock):
    client = app.test_client()
    data = {
        "purchase_date": datetime.now(ZoneInfo("Europe/Paris")).date().isoformat(),
        "quantity": JAVASCRIPT_MAX_SAFE_INTEGER,
    }
    assert purchase(client, stock.id, data).status_code == 201
    assert client.post(f"/api/stocks/{stock.id}/purchases", json=data).status_code == 400
    assert (
        client.post(
            f"/api/stocks/{stock.id}/purchases", json=[], headers={"Idempotency-Key": str(uuid4())}
        ).status_code
        == 400
    )


def test_sales_mix_sources_with_colliding_ids_and_protect_purchase(app, stock):
    client = app.test_client()
    saved = purchase(client, stock.id).get_json()
    assert saved["id"] == stock.grants[0].vestings[0].id
    allocations = [
        {"vesting_id": saved["id"], "quantity": 10},
        {"purchase_id": saved["id"], "quantity": 15},
    ]
    key = str(uuid4())
    response = sell(client, stock.id, allocations, token=key)
    assert response.status_code == 201
    sale = response.get_json()
    assert {tuple(sorted(row.items())) for row in sale["allocations"]} == {
        tuple(sorted(row.items())) for row in allocations
    }
    assert sell(client, stock.id, list(reversed(allocations)), token=key).get_json() == sale
    assert sell(client, stock.id, [{"purchase_id": saved["id"], "quantity": 6}]).status_code == 409
    assert (
        sell(
            client, stock.id, [{"purchase_id": saved["id"], "quantity": 5}], "2021-01-01"
        ).status_code
        == 400
    )
    assert (
        sell(
            client, stock.id, [{"purchase_id": saved["id"], "quantity": 5}], "2022-06-01"
        ).status_code
        == 201
    )
    endpoint = f"/api/stocks/{stock.id}/purchases/{saved['id']}"
    assert client.delete(endpoint).status_code == 409
    for sale in client.get(f"/api/stocks/{stock.id}/sales").get_json():
        assert client.delete(f"/api/stocks/{stock.id}/sales/{sale['id']}").status_code == 204
    assert client.delete(endpoint).status_code == 204


def test_source_validation_stock_scoping_and_archive_checks(app, stock):
    from app.stocks.models import Stock

    client = app.test_client()
    key = str(uuid4())
    saved = purchase(client, stock.id, token=key).get_json()
    other = Stock(family=stock.family, name="Microsoft", symbol="MSFT")
    db.session.add(other)
    db.session.commit()
    assert purchase(client, other.id, token=key).status_code == 201
    assert sell(client, other.id, [{"purchase_id": saved["id"], "quantity": 1}]).status_code == 400
    for allocations in (
        [{"purchase_id": saved["id"], "vesting_id": 1, "quantity": 1}],
        [{"quantity": 1}],
        [{"purchase_id": saved["id"], "quantity": 1}] * 2,
        [{"purchase_id": 9999, "quantity": 1}],
    ):
        assert sell(client, stock.id, allocations).status_code == 400
    assert client.delete(f"/api/stocks/{other.id}/purchases/{saved['id']}").status_code == 404
    for archived in (stock, stock.family):
        archived.is_archived = True
        db.session.commit()
        assert purchase(client, stock.id).status_code == 410
        assert client.get(f"/api/stocks/{stock.id}/purchases").status_code == 410
        assert client.delete(f"/api/stocks/{stock.id}/purchases/{saved['id']}").status_code == 410
        archived.is_archived = False
        db.session.commit()
    assert purchase(client, 9999).status_code == 404


def test_purchase_failure_rolls_back_and_can_retry(app, stock):
    from app.stocks.models import StockPurchase

    def fail(*args):
        raise SQLAlchemyError("simulated failure")

    event.listen(StockPurchase, "before_insert", fail)
    try:
        assert purchase(app.test_client(), stock.id).status_code == 500
        assert StockPurchase.query.count() == 0
    finally:
        event.remove(StockPurchase, "before_insert", fail)
    assert purchase(app.test_client(), stock.id).status_code == 201


def test_database_enforces_exactly_one_allocation_source(app, stock):
    from app.stocks.models import StockSaleAllocation

    client = app.test_client()
    saved = purchase(client, stock.id).get_json()
    sale = sell(client, stock.id, [{"purchase_id": saved["id"], "quantity": 1}]).get_json()
    for vesting_id, purchase_id in ((None, None), (stock.grants[0].vestings[0].id, saved["id"])):
        db.session.add(
            StockSaleAllocation(
                sale_id=sale["id"], vesting_id=vesting_id, purchase_id=purchase_id, quantity=1
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_concurrent_purchase_sales_cannot_oversell(app, stock):
    from app.stocks.models import StockSaleAllocation

    client = app.test_client()
    stock_id = stock.id
    purchase_id = purchase(client, stock_id).get_json()["id"]
    db.session.remove()
    barrier = Barrier(2)

    def attempt():
        with app.test_client() as client:
            barrier.wait()
            return sell(
                client, stock_id, [{"purchase_id": purchase_id, "quantity": 15}]
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: attempt(), range(2)))
    assert sorted(outcomes) == [201, 409]
    assert sum(row.quantity for row in StockSaleAllocation.query.all()) == 15
