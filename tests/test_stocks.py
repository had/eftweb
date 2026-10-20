from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

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
    family = Family(members=[FamilyMember(
        first_name="Ada", last_name="Lovelace", date_of_birth=date(1815, 12, 10),
        role="taxpayer1", position=1,
    )])
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
        "id": stock["id"], "family_id": family.id, "name": "Apple Inc.",
        "symbol": "AAPL", "is_archived": False,
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
    assert client.post(endpoint, json={"name": "Duplicate", "symbol": "brk-b"}).status_code == 409


def test_stock_symbols_are_unique_within_each_family_and_conflicts_roll_back(app):
    family1, family2 = create_family(), create_family()
    client = app.test_client()
    endpoint1 = f"/api/families/{family1.id}/stocks"
    endpoint2 = f"/api/families/{family2.id}/stocks"
    apple = client.post(endpoint1, json={"name": "Apple", "symbol": "AAPL"}).get_json()
    microsoft = client.post(endpoint1, json={"name": "Microsoft", "symbol": "MSFT"}).get_json()
    assert client.post(endpoint1, json={"name": "Duplicate", "symbol": " aapl "}).status_code == 409
    assert client.post(endpoint2, json={"name": "Apple", "symbol": "aapl"}).status_code == 201
    assert len(client.get(endpoint1).get_json()) == 2
    assert len(client.get(endpoint2).get_json()) == 1

    conflicting = client.put(
        f"/api/stocks/{microsoft['id']}", json={"name": "Changed", "symbol": "aapl"},
    )
    assert conflicting.status_code == 409
    assert client.get(endpoint1).get_json() == [apple, microsoft]
    # Editing a name without changing the ticker must remain possible.
    assert client.put(
        f"/api/stocks/{apple['id']}", json={"name": "Apple Inc.", "symbol": "aapl"},
    ).status_code == 200


@pytest.mark.parametrize("payload", [
    None, [], "stock", {}, {"name": "Apple"}, {"symbol": "AAPL"},
    {"name": " ", "symbol": "AAPL"}, {"name": 123, "symbol": "AAPL"},
    {"name": "x" * 257, "symbol": "AAPL"}, {"name": "Apple", "symbol": " "},
    {"name": "Apple", "symbol": True}, {"name": "Apple", "symbol": "x" * 17},
    {"name": "Apple", "symbol": "AA PL"}, {"name": "Apple", "symbol": "AA\tPL"},
])
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
    assert client.put(f"/api/stocks/{stock['id']}", json={"name": "X", "symbol": "X"}).status_code == 410
    assert client.delete(f"/api/stocks/{stock['id']}").status_code == 410
    assert db.session.get(Stock, stock["id"]).is_archived is False


def test_missing_stock_and_family_endpoints(app):
    client = app.test_client()
    assert client.get("/api/families/999/stocks").status_code == 404
    assert client.post("/api/families/999/stocks", json={"name": "X", "symbol": "X"}).status_code == 404
    assert client.put("/api/stocks/999", json={"name": "X", "symbol": "X"}).status_code == 404
    assert client.delete("/api/stocks/999").status_code == 404


def test_stock_database_constraint_and_family_relationship(app):
    from app.stocks.models import Stock

    family = create_family()
    stock = Stock(family=family, name="Apple", symbol="AAPL")
    db.session.add(stock)
    db.session.commit()
    db.session.add(Stock(family_id=family.id, name="Duplicate", symbol="AAPL"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert family.stocks == [stock]
    db.session.delete(family)
    db.session.commit()
    assert Stock.query.count() == 0
