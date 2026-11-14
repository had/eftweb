from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import create_app, db
from app.family.models import Family, FamilyMember
from config import TestingConfig


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def create_family():
    family = Family(
        members=[
            FamilyMember(
                first_name="Ada",
                last_name="Lovelace",
                date_of_birth=date(1815, 12, 10),
                role="taxpayer1",
                position=1,
            )
        ]
    )
    db.session.add(family)
    db.session.commit()
    return family


def test_stocks_can_be_created_edited_and_archived(app):
    from app.stocks.models import Stock

    family = create_family()
    client = app.test_client()
    endpoint = f"/api/families/{family.id}/stocks"
    assert client.get(endpoint).get_json() == []

    created = client.post(endpoint, json={"name": " Apple Inc. ", "symbol": " aapl "})
    assert created.status_code == 201
    stock = created.get_json()
    assert stock == {
        "id": stock["id"],
        "family_id": family.id,
        "name": "Apple Inc.",
        "symbol": "AAPL",
        "is_archived": False,
    }
    stock_endpoint = f"/api/stocks/{stock['id']}"
    assert client.get(endpoint).get_json() == [stock]
    # Discard the identity map to check persistence through another database read.
    db.session.expire_all()
    assert db.session.get(Stock, stock["id"]).name == "Apple Inc."

    updated = client.put(stock_endpoint, json={"name": "Berkshire Hathaway", "symbol": "brk-b"})
    assert updated.status_code == 200
    assert updated.get_json()["symbol"] == "BRK-B"
    assert client.get(endpoint).get_json() == [updated.get_json()]

    assert client.delete(stock_endpoint).status_code == 200
    assert client.get(endpoint).get_json() == []
    archived = client.get(f"{endpoint}?archived=true").get_json()
    assert archived == [{**updated.get_json(), "is_archived": True}]
    assert db.session.get(Stock, stock["id"]).is_archived is True
    assert client.put(stock_endpoint, json={"name": "Other", "symbol": "OTHER"}).status_code == 410
    assert client.delete(stock_endpoint).status_code == 410
    assert (
        client.post(endpoint, json={"name": "Other broker", "symbol": "brk-b"}).status_code == 201
    )
    restored = client.post(f"{stock_endpoint}/restore")
    assert restored.status_code == 200
    assert restored.get_json() == updated.get_json()
    assert len(client.get(endpoint).get_json()) == 2
    assert client.get(f"{endpoint}?archived=true").get_json() == []
    assert client.post(f"{stock_endpoint}/restore").status_code == 409


def test_multiple_stocks_in_a_family_can_share_a_normalized_ticker(app):
    family1, family2 = create_family(), create_family()
    client = app.test_client()
    endpoint1 = f"/api/families/{family1.id}/stocks"
    endpoint2 = f"/api/families/{family2.id}/stocks"
    apple = client.post(endpoint1, json={"name": "Apple", "symbol": "AAPL"}).get_json()
    microsoft = client.post(endpoint1, json={"name": "Microsoft", "symbol": "MSFT"}).get_json()
    duplicate = client.post(endpoint1, json={"name": "Other broker", "symbol": " aapl "})
    assert duplicate.status_code == 201
    assert duplicate.get_json()["symbol"] == "AAPL"
    assert duplicate.get_json()["id"] != apple["id"]
    assert client.post(endpoint2, json={"name": "Apple", "symbol": "aapl"}).status_code == 201
    assert len(client.get(endpoint1).get_json()) == 3
    assert len(client.get(endpoint2).get_json()) == 1

    changed = client.put(
        f"/api/stocks/{microsoft['id']}",
        json={"name": "Changed", "symbol": "aapl"},
    )
    assert changed.status_code == 200
    assert changed.get_json()["symbol"] == "AAPL"
    assert changed.get_json()["id"] == microsoft["id"]
    # Editing a name without changing the ticker must remain possible.
    assert (
        client.put(
            f"/api/stocks/{apple['id']}",
            json={"name": "Apple Inc.", "symbol": "aapl"},
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "stock",
        {},
        {"name": "Apple"},
        {"symbol": "AAPL"},
        {"name": " ", "symbol": "AAPL"},
        {"name": 123, "symbol": "AAPL"},
        {"name": "x" * 257, "symbol": "AAPL"},
        {"name": "Apple", "symbol": " "},
        {"name": "Apple", "symbol": True},
        {"name": "Apple", "symbol": "x" * 17},
        {"name": "Apple", "symbol": "AA PL"},
        {"name": "Apple", "symbol": "AA\tPL"},
    ],
)
def test_invalid_stock_payloads_do_not_create_or_change_stocks(app, payload):
    family = create_family()
    client = app.test_client()
    endpoint = f"/api/families/{family.id}/stocks"
    stock = client.post(endpoint, json={"name": "Apple", "symbol": "AAPL"}).get_json()
    assert client.post(endpoint, json=payload).status_code == 400
    assert client.put(f"/api/stocks/{stock['id']}", json=payload).status_code == 400
    assert client.get(endpoint).get_json() == [stock]


def test_archived_families_cannot_list_create_edit_or_archive_stocks(app):
    from app.stocks.models import Stock

    family = create_family()
    client = app.test_client()
    endpoint = f"/api/families/{family.id}/stocks"
    stock = client.post(endpoint, json={"name": "Apple", "symbol": "AAPL"}).get_json()
    client.delete(f"/api/families/{family.id}")
    assert client.get(endpoint).status_code == 410
    assert client.get(f"{endpoint}?archived=true").status_code == 410
    assert client.post(endpoint, json={"name": "Microsoft", "symbol": "MSFT"}).status_code == 410
    assert (
        client.put(f"/api/stocks/{stock['id']}", json={"name": "X", "symbol": "X"}).status_code
        == 410
    )
    assert client.delete(f"/api/stocks/{stock['id']}").status_code == 410
    assert client.delete(f"/api/stocks/{stock['id']}?permanent=true").status_code == 410
    assert client.post(f"/api/stocks/{stock['id']}/restore").status_code == 410
    assert db.session.get(Stock, stock["id"]).is_archived is False


def test_missing_stock_and_family_endpoints(app):
    client = app.test_client()
    assert client.get("/api/families/999/stocks").status_code == 404
    assert (
        client.post("/api/families/999/stocks", json={"name": "X", "symbol": "X"}).status_code
        == 404
    )
    assert client.put("/api/stocks/999", json={"name": "X", "symbol": "X"}).status_code == 404
    assert client.delete("/api/stocks/999").status_code == 404
    assert client.delete("/api/stocks/999?permanent=true").status_code == 404
    assert client.post("/api/stocks/999/restore").status_code == 404


def test_stock_database_allows_duplicate_tickers_and_keeps_family_relationship(app):
    from app.stocks.models import Stock

    family = create_family()
    stock = Stock(family=family, name="Apple", symbol="AAPL")
    db.session.add(stock)
    db.session.commit()
    other = Stock(family_id=family.id, name="Other broker", symbol="AAPL")
    db.session.add(other)
    db.session.commit()
    assert family.stocks == [stock, other]
    db.session.delete(family)
    db.session.commit()
    assert Stock.query.count() == 0


def populated_stock(family, name):
    from app.stocks.models import (
        GrantVesting,
        Stock,
        StockGrant,
        StockImportReceipt,
        StockPurchase,
        StockSale,
        StockSaleAllocation,
    )

    stock = Stock(family=family, name=name, symbol="AAPL")
    stock.grants = [
        StockGrant(
            title="Grant",
            grant_number="123",
            grant_date=date(2020, 1, 1),
            quantity=10,
            vesting_start_date=date(2020, 1, 1),
            schedule_type="quarterly",
            customized=True,
            creation_token="grant-key",
            request_hash="grant-hash",
            vestings=[GrantVesting(date=date(2021, 1, 1), quantity=10)],
        )
    ]
    stock.purchases = [
        StockPurchase(
            purchase_date=date(2021, 1, 1),
            quantity=10,
            plan_name="ESPP",
            creation_token="purchase-key",
            request_hash="purchase-hash",
        )
    ]
    db.session.add(stock)
    db.session.flush()
    stock.sales = [
        StockSale(
            transaction_date=date(2022, 1, 1),
            quantity=4,
            proceeds_per_share=100,
            currency="USD",
            creation_token="sale-key",
            request_hash="sale-hash",
            allocations=[
                StockSaleAllocation(vesting_id=stock.grants[0].vestings[0].id, quantity=2),
                StockSaleAllocation(purchase_id=stock.purchases[0].id, quantity=2),
            ],
        )
    ]
    stock.import_receipts = [
        StockImportReceipt(
            creation_token="import-key",
            request_hash="import-hash",
            result={"sales": 1},
        )
    ]
    db.session.commit()
    return stock


def test_restore_preserves_all_records_and_same_ticker_holdings_are_independent(app):
    family = create_family()
    stock = populated_stock(family, "Ada's broker")
    other = populated_stock(family, "Partner's broker")
    client = app.test_client()
    endpoint = f"/api/stocks/{stock.id}"
    other_endpoint = f"/api/stocks/{other.id}"
    before = {
        path: client.get(f"{endpoint}/{path}").get_json()
        for path in ("grants", "purchases", "sales")
    }
    other_before = client.get(f"{other_endpoint}/sales").get_json()
    assert client.delete(endpoint).status_code == 200
    assert client.get(f"{endpoint}/sales").status_code == 410
    assert client.post(f"{endpoint}/restore").status_code == 200
    for path, data in before.items():
        assert client.get(f"{endpoint}/{path}").get_json() == data
    assert client.get(f"{other_endpoint}/sales").get_json() == other_before
    assert len(stock.import_receipts) == 1


def test_permanent_delete_removes_all_records_with_foreign_keys_and_preserves_other_holdings(app):
    from app.stocks.models import (
        GrantVesting,
        Stock,
        StockGrant,
        StockImportReceipt,
        StockPurchase,
        StockSale,
        StockSaleAllocation,
    )

    db.session.execute(text("PRAGMA foreign_keys=ON"))
    family = create_family()
    stock = populated_stock(family, "Ada's broker")
    other = populated_stock(family, "Partner's broker")
    stock_id, other_id, family_id = stock.id, other.id, family.id
    client = app.test_client()
    endpoint = f"/api/stocks/{stock_id}"
    other_before = client.get(f"/api/stocks/{other_id}/sales").get_json()
    assert client.delete(f"{endpoint}?permanent=true").status_code == 409
    assert client.delete(endpoint).status_code == 200
    assert client.delete(f"{endpoint}?permanent=true").status_code == 204
    db.session.expire_all()
    assert db.session.get(Stock, stock_id) is None
    assert db.session.get(Family, family_id) is not None
    assert Stock.query.count() == 1
    for model in (StockGrant, GrantVesting, StockPurchase, StockSale, StockImportReceipt):
        assert model.query.count() == 1
    assert StockSaleAllocation.query.count() == 2
    assert db.session.execute(text("PRAGMA foreign_key_check")).all() == []
    assert client.get(f"/api/stocks/{other_id}/sales").get_json() == other_before
    assert client.post(f"{endpoint}/restore").status_code == 404
    assert client.delete(f"{endpoint}?permanent=true").status_code == 404
    created = client.post(
        f"/api/families/{family_id}/stocks", json={"name": "New", "symbol": "AAPL"}
    )
    assert created.get_json()["id"] > max(stock_id, other_id)


@pytest.mark.parametrize("action", ["restore", "delete"])
def test_failed_archive_actions_roll_back_and_can_be_retried(app, monkeypatch, action):
    from app.stocks.models import Stock, StockSaleAllocation

    family = create_family()
    stock = populated_stock(family, "Ada's broker")
    stock_id = stock.id
    client = app.test_client()
    endpoint = f"/api/stocks/{stock_id}"
    assert client.delete(endpoint).status_code == 200
    request_action = (
        (lambda: client.post(f"{endpoint}/restore"))
        if action == "restore"
        else (lambda: client.delete(f"{endpoint}?permanent=true"))
    )
    with monkeypatch.context() as patch:

        def fail_commit():
            raise SQLAlchemyError("Database unavailable")

        patch.setattr(db.session, "commit", fail_commit)
        assert request_action().status_code == 500
    db.session.expire_all()
    assert db.session.get(Stock, stock_id).is_archived is True
    assert StockSaleAllocation.query.count() == 2
    assert request_action().status_code == (200 if action == "restore" else 204)
