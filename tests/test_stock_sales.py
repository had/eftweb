from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError

from app import create_app, db
from app.constants import JAVASCRIPT_MAX_SAFE_INTEGER
from config import TestingConfig


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'sales.sqlite'}"
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
            title="Grant",
            grant_date=date(2020, 1, 1),
            quantity=150,
            vesting_start_date=date(2020, 1, 1),
            schedule_type="quarterly",
            customized=True,
            creation_token=str(uuid4()),
            request_hash="hash",
            vestings=[
                GrantVesting(date=date(2021, 1, 1), quantity=100),
                GrantVesting(date=date(2022, 1, 1), quantity=50),
            ],
        )
    ]
    db.session.add(stock)
    db.session.commit()
    return stock


def payload(stock, **overrides):
    return {
        "transaction_date": "2023-01-01",
        "quantity": 30,
        "proceeds_per_share": "123.456789",
        "allocations": [{"vesting_id": stock.grants[0].vestings[0].id, "quantity": 30}],
        **overrides,
    }


def post(client, stock, data=None, token=None):
    data = payload(stock) if data is None else data
    if isinstance(data, dict) and isinstance(data.get("allocations"), list):
        data = {
            **data,
            "allocations": [
                {**row, "acquisition_fmv": "100.000000"} if isinstance(row, dict) else row
                for row in data["allocations"]
            ],
        }
    return client.post(
        f"/api/stocks/{stock.id}/sales",
        json=data,
        headers={"Idempotency-Key": token or str(uuid4())},
    )


def test_delete_all_sales_restores_lots_across_years_and_keeps_other_stocks(app, stock):
    from app.stocks.models import Stock, StockPurchase, StockSaleAllocation

    client = app.test_client()
    post(client, stock)
    post(client, stock, payload(stock, transaction_date="2024-01-01"))
    purchase = StockPurchase(
        stock_id=stock.id,
        purchase_date=date(2021, 1, 1),
        quantity=10,
        plan_name="ESPP",
        acquisition_fmv=100,
        creation_token=str(uuid4()),
        request_hash="purchase",
    )
    other = Stock(family=stock.family, name="Other holding", symbol=stock.symbol)
    other_purchase = StockPurchase(
        stock=other,
        purchase_date=date(2021, 1, 1),
        quantity=10,
        plan_name="ESPP",
        acquisition_fmv=100,
        creation_token=str(uuid4()),
        request_hash="other",
    )
    db.session.add_all([purchase, other_purchase])
    db.session.commit()
    assert (
        post(
            client,
            stock,
            payload(stock, quantity=5, allocations=[{"purchase_id": purchase.id, "quantity": 5}]),
        ).status_code
        == 201
    )
    assert (
        post(
            client,
            other,
            {
                "transaction_date": "2024-01-01",
                "quantity": 5,
                "proceeds_per_share": "110",
                "allocations": [{"purchase_id": other_purchase.id, "quantity": 5}],
            },
        ).status_code
        == 201
    )
    grants = client.get(f"/api/stocks/{stock.id}/grants").get_json()
    purchases = client.get(f"/api/stocks/{stock.id}/purchases").get_json()
    other_sales = client.get(f"/api/stocks/{other.id}/sales").get_json()
    endpoint = f"/api/stocks/{stock.id}/sales"
    assert len(client.get(endpoint).get_json()) == 3
    assert client.delete(endpoint).status_code == 204
    assert client.get(endpoint).get_json() == []
    assert client.get(f"/api/stocks/{stock.id}/grants").get_json() == grants
    assert client.get(f"/api/stocks/{stock.id}/purchases").get_json() == purchases
    assert client.get(f"/api/stocks/{other.id}/sales").get_json() == other_sales
    assert StockSaleAllocation.query.count() == 1
    assert client.delete(endpoint).status_code == 204
    # The original lot's full balance is available again.
    assert (
        post(
            client,
            stock,
            payload(
                stock,
                quantity=100,
                allocations=[{"vesting_id": stock.grants[0].vestings[0].id, "quantity": 100}],
            ),
        ).status_code
        == 201
    )


def test_delete_all_sales_is_atomic_and_retryable(app, stock):
    from app.stocks.models import StockSale, StockSaleAllocation

    client = app.test_client()
    post(client, stock)
    post(client, stock, payload(stock, transaction_date="2024-01-01"))
    endpoint = f"/api/stocks/{stock.id}/sales"
    original = client.get(endpoint).get_json()
    deleted = []

    def fail_second_delete(mapper, connection, target):
        deleted.append(target.id)
        if len(deleted) == 2:
            raise SQLAlchemyError("Simulated later deletion failure")

    event.listen(StockSale, "before_delete", fail_second_delete)
    try:
        assert client.delete(endpoint).status_code == 500
    finally:
        event.remove(StockSale, "before_delete", fail_second_delete)
    assert client.get(endpoint).get_json() == original
    assert StockSaleAllocation.query.count() == 2
    assert client.delete(endpoint).status_code == 204
    assert StockSaleAllocation.query.count() == 0


def test_delete_all_sales_respects_missing_and_archive_rules(app, stock):
    client = app.test_client()
    endpoint = f"/api/stocks/{stock.id}/sales"
    post(client, stock)
    assert client.delete("/api/stocks/999999/sales").status_code == 404
    for archived_family in (False, True):
        stock.is_archived = not archived_family
        stock.family.is_archived = archived_family
        db.session.commit()
        assert client.delete(endpoint).status_code == 410


def test_round_trip_multiple_pockets_idempotent_retry_and_grant_protection(app, stock):
    from app.stocks.models import Stock, StockSale, StockSaleAllocation

    client = app.test_client()
    pockets = stock.grants[0].vestings
    grant_id = stock.grants[0].id
    endpoint = f"/api/stocks/{stock.id}/sales"
    assert client.get(endpoint).get_json() == []
    data = payload(
        stock,
        quantity=120,
        allocations=[
            {"vesting_id": pockets[0].id, "quantity": 80},
            {"vesting_id": pockets[1].id, "quantity": 40},
        ],
    )
    key = str(uuid4())
    response = post(client, stock, data, key)
    assert response.status_code == 201
    saved = response.get_json()
    assert saved["proceeds_per_share"] == "123.456789"
    assert saved["currency"] == "USD"
    assert saved["allocations"] == data["allocations"]
    repeated = post(
        client, stock, {**data, "allocations": list(reversed(data["allocations"]))}, key
    )
    assert repeated.status_code == 200  # Replay precedes availability checks.
    assert repeated.get_json() == saved
    assert post(client, stock, {**data, "proceeds_per_share": "125"}, key).status_code == 409
    stock_id = stock.id
    db.session.remove()
    stock = db.session.get(Stock, stock_id)
    assert client.get(endpoint).get_json() == [saved]
    protected = client.delete(f"/api/stocks/{stock.id}/grants/{grant_id}")
    assert protected.status_code == 409
    assert "recorded sales" in protected.get_json()["error"]
    assert client.delete(f"{endpoint}/{saved['id']}").status_code == 204
    assert client.get(endpoint).get_json() == []
    assert StockSale.query.count() == StockSaleAllocation.query.count() == 0
    assert post(client, stock, data).status_code == 201
    second_id = client.get(endpoint).get_json()[0]["id"]
    assert client.delete(f"{endpoint}/{second_id}").status_code == 204
    assert client.delete(f"/api/stocks/{stock.id}/grants/{grant_id}").status_code == 204


def test_backdated_and_repeated_sales_cannot_reuse_later_allocated_shares(app, stock):
    client = app.test_client()
    assert post(client, stock, payload(stock, transaction_date="2024-01-01")).status_code == 201
    assert post(client, stock, payload(stock, transaction_date="2022-01-01")).status_code == 201
    data = payload(
        stock,
        quantity=41,
        allocations=[{"vesting_id": stock.grants[0].vestings[0].id, "quantity": 41}],
    )
    assert post(client, stock, data).status_code == 409
    data["quantity"] = data["allocations"][0]["quantity"] = 40
    assert post(client, stock, data).status_code == 201
    assert post(client, stock).status_code == 409


@pytest.mark.parametrize("price", ["0.000001", "99999999.999999", "100.000000"])
def test_six_decimal_price_boundaries_are_preserved(app, stock, price):
    response = post(app.test_client(), stock, payload(stock, proceeds_per_share=price))
    assert response.status_code == 201
    assert response.get_json()["proceeds_per_share"] == price


def test_sale_can_allocate_across_grants_and_keys_are_stock_scoped(app, stock):
    from app.stocks.models import GrantVesting, Stock, StockGrant

    family_id = stock.family_id
    grant = StockGrant(
        stock=stock,
        title="Second grant",
        grant_date=date(2020, 1, 1),
        quantity=50,
        vesting_start_date=date(2020, 1, 1),
        schedule_type="quarterly",
        customized=True,
        creation_token=str(uuid4()),
        request_hash="hash",
        vestings=[GrantVesting(date=date(2021, 1, 1), quantity=50)],
    )
    other = Stock(family_id=family_id, name="Microsoft", symbol="MSFT")
    db.session.add_all([grant, other])
    db.session.commit()
    data = payload(
        stock,
        quantity=60,
        allocations=[
            {"vesting_id": stock.grants[0].vestings[0].id, "quantity": 30},
            {"vesting_id": grant.vestings[0].id, "quantity": 30},
        ],
    )
    key = str(uuid4())
    assert post(app.test_client(), stock, data, key).status_code == 201
    client = app.test_client()
    other_grant = client.post(
        f"/api/stocks/{other.id}/grants",
        json={
            "title": "Other stock grant",
            "grant_date": "2020-01-01",
            "quantity": 50,
            "vesting_start_date": "2020-01-01",
            "schedule_type": "quarterly",
            "customized": True,
            "vestings": [{"date": "2021-01-01", "quantity": 50}],
        },
        headers={"Idempotency-Key": str(uuid4())},
    ).get_json()
    other_data = {
        **data,
        "quantity": 30,
        "allocations": [{"vesting_id": other_grant["vestings"][0]["id"], "quantity": 30}],
    }
    assert post(client, other, other_data, key).status_code == 201


@pytest.mark.parametrize(
    "changes",
    [
        {"transaction_date": "2023-02-29"},
        {"transaction_date": "9999-01-01"},
        {"transaction_date": "2020-12-31"},
        {"transaction_date": None},
        {"quantity": True},
        {"quantity": 0},
        {"quantity": -2},
        {"quantity": 1.5},
        {"quantity": "30"},
        {"quantity": JAVASCRIPT_MAX_SAFE_INTEGER + 1},
        {"proceeds_per_share": "0"},
        {"proceeds_per_share": "-1"},
        {"proceeds_per_share": True},
        {"proceeds_per_share": "NaN"},
        {"proceeds_per_share": "Infinity"},
        {"proceeds_per_share": "1.0000001"},
        {"proceeds_per_share": "100000000"},
        {"proceeds_per_share": None},
        {"proceeds_per_share": "1e99999"},
        {"currency": "EUR"},
        {"allocations": []},
        {"allocations": None},
        {"allocations": [None]},
        {"allocations": [{"vesting_id": 9999, "quantity": 30}]},
        {"allocations": [{"vesting_id": True, "quantity": 30}]},
    ],
)
def test_invalid_sales_leave_no_partial_records(app, stock, changes):
    from app.stocks.models import StockSale, StockSaleAllocation

    assert post(app.test_client(), stock, payload(stock, **changes)).status_code == 400
    assert StockSale.query.count() == StockSaleAllocation.query.count() == 0


def test_duplicate_allocations_mismatched_totals_and_invalid_allocation_quantities(app, stock):
    client = app.test_client()
    pocket_id = stock.grants[0].vestings[0].id
    for allocations in (
        [{"vesting_id": pocket_id, "quantity": 15}] * 2,
        [{"vesting_id": pocket_id, "quantity": 29}],
        [{"vesting_id": pocket_id, "quantity": True}],
        [{"vesting_id": pocket_id, "quantity": -30}],
        [{"vesting_id": pocket_id, "quantity": 30.0}],
    ):
        assert post(client, stock, payload(stock, allocations=allocations)).status_code == 400


def test_stock_isolation_archives_and_request_validation(app, stock):
    from app.stocks.models import Stock

    client = app.test_client()
    saved = post(client, stock).get_json()
    other = Stock(family_id=stock.family_id, name="Other", symbol="MSFT")
    db.session.add(other)
    db.session.commit()
    endpoint = f"/api/stocks/{stock.id}/sales"
    assert client.get(f"/api/stocks/{other.id}/sales").get_json() == []
    assert post(client, other, payload(stock)).status_code == 400
    assert client.delete(f"/api/stocks/{other.id}/sales/{saved['id']}").status_code == 404
    assert client.get("/api/stocks/9999/sales").status_code == 404
    assert client.post("/api/stocks/9999/sales").status_code == 404
    assert client.delete("/api/stocks/9999/sales/1").status_code == 404
    assert client.post(endpoint, json=payload(stock)).status_code == 400
    assert (
        client.post(endpoint, json=[], headers={"Idempotency-Key": str(uuid4())}).status_code == 400
    )
    for archive_family in (False, True):
        stock.is_archived = not archive_family
        stock.family.is_archived = archive_family
        db.session.commit()
        assert client.get(endpoint).status_code == 410
        assert post(client, stock).status_code == 410
        assert client.delete(f"{endpoint}/{saved['id']}").status_code == 410


def test_failed_sale_writes_and_deletes_roll_back_and_remain_retryable(app, stock):
    from app.stocks.models import StockSale, StockSaleAllocation

    def fail(*_):
        raise SQLAlchemyError("Simulated write failure")

    key = str(uuid4())
    event.listen(StockSaleAllocation, "before_insert", fail)
    try:
        assert post(app.test_client(), stock, token=key).status_code == 500
    finally:
        event.remove(StockSaleAllocation, "before_insert", fail)
    assert StockSale.query.count() == StockSaleAllocation.query.count() == 0
    saved = post(app.test_client(), stock, token=key).get_json()
    endpoint = f"/api/stocks/{stock.id}/sales/{saved['id']}"
    event.listen(StockSale, "before_delete", fail)
    try:
        assert app.test_client().delete(endpoint).status_code == 500
    finally:
        event.remove(StockSale, "before_delete", fail)
    assert StockSale.query.count() == StockSaleAllocation.query.count() == 1
    assert app.test_client().delete(endpoint).status_code == 204
    assert app.test_client().delete(endpoint).status_code == 404


@pytest.mark.parametrize("same_token", [False, True])
def test_concurrent_sales_cannot_oversell_a_pocket(app, stock, same_token):
    from app.stocks.models import StockSaleAllocation

    data = payload(
        stock,
        quantity=70,
        allocations=[
            {
                "vesting_id": stock.grants[0].vestings[0].id,
                "quantity": 70,
                "acquisition_fmv": "100.000000",
            }
        ],
    )
    endpoint = f"/api/stocks/{stock.id}/sales"
    db.session.remove()
    barrier = Barrier(2)
    token = str(uuid4())

    def sell():
        with app.test_client() as client:
            barrier.wait(timeout=5)
            return client.post(
                endpoint,
                json=data,
                headers={"Idempotency-Key": token if same_token else str(uuid4())},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(lambda _: sell(), range(2)))
    assert statuses == ([200, 201] if same_token else [201, 409])
    assert sum(row.quantity for row in StockSaleAllocation.query.all()) == 70
