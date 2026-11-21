from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError

from app import create_app, db
from app.constants import JAVASCRIPT_MAX_SAFE_INTEGER
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


@pytest.fixture()
def stock(app):
    from app.family.models import Family
    from app.stocks.models import Stock

    family = Family()
    stock = Stock(family=family, name="Apple", symbol="AAPL")
    db.session.add(stock)
    db.session.commit()
    return stock


def payload(**overrides):
    data = {
        "title": "Adjusted grant",
        "grant_date": "2026-10-25",
        "quantity": 100,
        "vesting_start_date": "2025-01-31",
        "schedule_type": "quarterly",
        "customized": True,
        "vestings": [
            {"date": "2030-01-31", "quantity": 30},
            {"date": "2026-10-25", "quantity": 20},
            {"date": "2026-10-25", "quantity": 50},
        ],
    }
    return {**data, **overrides}


def post(client, stock, data=None, token=None):
    return client.post(
        f"/api/stocks/{stock.id}/grants",
        json=payload() if data is None else data,
        headers={"Idempotency-Key": token or str(uuid4())},
    )


def test_grants_round_trip_exact_release_schedule_and_delete_children(app, stock):
    from app.stocks.models import GrantVesting, StockGrant

    client = app.test_client()
    endpoint = f"/api/stocks/{stock.id}/grants"
    assert client.get(f"/api/stocks/{stock.id}").get_json() == stock.to_dict()
    assert client.get(endpoint).get_json() == []
    response = post(client, stock)
    assert response.status_code == 201
    saved = response.get_json()
    assert saved["stock_id"] == stock.id
    for field in (
        "title",
        "grant_date",
        "quantity",
        "vesting_start_date",
        "schedule_type",
        "customized",
    ):
        assert saved[field] == payload()[field]
    assert [{k: row[k] for k in ("date", "quantity")} for row in saved["vestings"]] == sorted(
        payload()["vestings"], key=lambda row: (row["date"], row["quantity"])
    )
    assert all(isinstance(row["id"], int) for row in saved["vestings"])
    db.session.remove()
    assert client.get(endpoint).get_json() == [saved]
    assert StockGrant.query.count() == 1
    assert GrantVesting.query.count() == 3
    assert client.delete(f"{endpoint}/{saved['id']}").status_code == 204
    db.session.remove()
    assert client.get(endpoint).get_json() == []
    assert StockGrant.query.count() == GrantVesting.query.count() == 0
    assert client.delete(f"{endpoint}/{saved['id']}").status_code == 404


def test_create_is_idempotent_but_duplicate_titles_and_stock_scoped_keys_are_allowed(app, stock):
    from app.stocks.models import Stock, StockGrant

    client = app.test_client()
    key = str(uuid4())
    created = post(client, stock, token=key)
    repeated = post(
        client, stock, {**payload(), "vestings": list(reversed(payload()["vestings"]))}, key
    )
    assert repeated.status_code == 200
    assert repeated.get_json() == created.get_json()
    assert post(client, stock, payload(title="Different"), key).status_code == 409
    assert StockGrant.query.count() == 1
    assert post(client, stock).status_code == 201
    other = Stock(family_id=stock.family_id, name="Other", symbol="MSFT")
    db.session.add(other)
    db.session.commit()
    assert post(client, other, token=key).status_code == 201
    assert StockGrant.query.count() == 3


@pytest.mark.parametrize(
    "changes",
    [
        {"title": None},
        {"title": "x" * 257},
        {"grant_date": "2026-02-30"},
        {"grant_date": "20261025"},
        {"grant_date": None},
        {"vesting_start_date": "2025-02-29"},
        {"quantity": True},
        {"quantity": 0},
        {"quantity": 1.5},
        {"quantity": "100"},
        {"quantity": JAVASCRIPT_MAX_SAFE_INTEGER + 1},
        {"schedule_type": "unknown"},
        {"customized": "true"},
        {"vestings": []},
        {"vestings": None},
        {"vestings": [None]},
        {"vestings": [{"date": "2026-10-25", "quantity": 99}]},
        {"vestings": [{"date": "2026-10-25", "quantity": True}]},
        {"vestings": [{"date": "2026-10-25", "quantity": -100}]},
        {"vestings": [{"date": "2026-10-25", "quantity": 100.0}]},
        {"vestings": [{"date": "2026-04-31", "quantity": 100}]},
    ],
)
def test_invalid_payloads_leave_no_partial_grant_or_releases(app, stock, changes):
    from app.stocks.models import GrantVesting, StockGrant

    response = post(app.test_client(), stock, payload(**changes))
    assert response.status_code == 400
    assert response.get_json()["error"]
    assert StockGrant.query.count() == GrantVesting.query.count() == 0


def test_missing_payload_and_token_default_title_and_chronological_order(app, stock):
    client = app.test_client()
    endpoint = f"/api/stocks/{stock.id}/grants"
    assert client.post(endpoint, json=payload()).status_code == 400
    assert (
        client.post(endpoint, json=payload(), headers={"Idempotency-Key": "bad"}).status_code == 400
    )
    assert (
        client.post(endpoint, json=[], headers={"Idempotency-Key": str(uuid4())}).status_code == 400
    )
    later = post(client, stock, payload(title=" ")).get_json()
    earlier = post(client, stock, payload(grant_date="2020-01-01")).get_json()
    assert later["title"] == "AAPL-2026-10-25"
    assert client.get(endpoint).get_json() == [earlier, later]


def test_failed_insert_rolls_back_parent_and_children_and_can_be_retried(app, stock):
    from app.stocks.models import GrantVesting, StockGrant

    def fail_insert(*_):
        raise SQLAlchemyError("Simulated release write failure")

    event.listen(GrantVesting, "before_insert", fail_insert)
    token = str(uuid4())
    try:
        assert post(app.test_client(), stock, token=token).status_code == 500
    finally:
        event.remove(GrantVesting, "before_insert", fail_insert)
    assert StockGrant.query.count() == GrantVesting.query.count() == 0
    assert post(app.test_client(), stock, token=token).status_code == 201


def test_stock_isolation_and_archived_resource_rules(app, stock):
    from app.stocks.models import Stock

    client = app.test_client()
    saved = post(client, stock).get_json()
    other = Stock(family_id=stock.family_id, name="Other", symbol="MSFT")
    db.session.add(other)
    db.session.commit()
    assert client.get(f"/api/stocks/{other.id}/grants").get_json() == []
    assert client.delete(f"/api/stocks/{other.id}/grants/{saved['id']}").status_code == 404
    assert client.get("/api/stocks/9999").status_code == 404
    assert client.get("/api/stocks/9999/grants").status_code == 404
    assert client.delete(f"/api/stocks/9999/grants/{saved['id']}").status_code == 404
    for archive_family in (False, True):
        stock.is_archived = not archive_family
        stock.family.is_archived = archive_family
        db.session.commit()
        assert client.get(f"/api/stocks/{stock.id}").status_code == 410
        assert client.get(f"/api/stocks/{stock.id}/grants").status_code == 410
        assert post(client, stock).status_code == 410
        assert client.delete(f"/api/stocks/{stock.id}/grants/{saved['id']}").status_code == 410


def test_failed_delete_preserves_the_grant_and_releases(app, stock):
    from app.stocks.models import GrantVesting, StockGrant

    client = app.test_client()
    saved = post(client, stock).get_json()

    def fail_delete(*_):
        raise SQLAlchemyError("Simulated delete failure")

    event.listen(StockGrant, "before_delete", fail_delete)
    try:
        assert client.delete(f"/api/stocks/{stock.id}/grants/{saved['id']}").status_code == 500
    finally:
        event.remove(StockGrant, "before_delete", fail_delete)
    assert StockGrant.query.count() == 1
    assert GrantVesting.query.count() == 3
    assert client.get(f"/api/stocks/{stock.id}/grants").get_json() == [saved]


def test_edit_grant_metadata_preserves_acquisitions_and_creation_retry(app, stock):
    from datetime import date

    from app.family.models import FamilyMember
    from app.stocks.models import StockGrant

    stock.family.members.append(
        FamilyMember(
            role="taxpayer1",
            position=1,
            first_name="Ada",
            last_name="Example",
            date_of_birth=date(1980, 1, 1),
        )
    )
    db.session.commit()
    client = app.test_client()
    token = str(uuid4())
    saved = post(client, stock, token=token).get_json()
    endpoint = f"/api/stocks/{stock.id}/grants/{saved['id']}"
    changes = {
        "title": "  Updated award  ",
        "grant_number": "  000234  ",
        "grant_date": "2020-01-02",
        "approval_date": "2016-12-31",
        "taxpayer_role": "taxpayer1",
    }
    response = client.patch(endpoint, json=changes)
    assert response.status_code == 200
    updated = response.get_json()
    assert updated["title"] == "Updated award"
    assert updated["grant_number"] == "000234"
    for field in ("grant_date", "approval_date", "taxpayer_role"):
        assert updated[field] == changes[field]
    for field in ("vestings", "quantity", "vesting_start_date", "schedule_type", "customized"):
        assert updated[field] == saved[field]
    # Correcting metadata does not change the identity of an already-created grant.
    assert post(client, stock, token=token).get_json() == updated
    assert StockGrant.query.count() == 1
    cleared = client.patch(
        endpoint, json={"approval_date": None, "taxpayer_role": None, "grant_number": None}
    ).get_json()
    assert all(
        cleared[field] is None for field in ("approval_date", "taxpayer_role", "grant_number")
    )
    default_title = client.patch(
        endpoint, json={"title": " ", "grant_date": "2021-01-02"}
    ).get_json()
    assert default_title["title"] == "AAPL-2021-01-02"


@pytest.mark.parametrize(
    "changes",
    [
        {},
        [],
        {"quantity": 1},
        {"vestings": []},
        {"grant_date": "2026-02-30"},
        {"grant_date": None},
        {"approval_date": "2015-08-07"},
        {"approval_date": "2026-02-30"},
        {"approval_date": ""},
        {"taxpayer_role": "taxpayer2"},
        {"taxpayer_role": ["taxpayer1"]},
        {"title": None},
        {"title": "x" * 257},
    ],
)
def test_invalid_metadata_edit_is_atomic(app, stock, changes):
    client = app.test_client()
    saved = post(client, stock).get_json()
    endpoint = f"/api/stocks/{stock.id}/grants/{saved['id']}"
    body = (
        {"grant_number": "CHANGED", **changes} if isinstance(changes, dict) and changes else changes
    )
    assert client.patch(endpoint, json=body).status_code == 400
    assert client.get(f"/api/stocks/{stock.id}/grants").get_json() == [saved]


def test_metadata_edit_scope_archives_uniqueness_and_commit_failure(app, stock):
    from app.stocks.models import Stock, StockGrant

    client = app.test_client()
    saved = post(client, stock, payload(grant_number="001")).get_json()
    other_grant = post(client, stock, payload(grant_number="002")).get_json()
    endpoint = f"/api/stocks/{stock.id}/grants/{saved['id']}"
    assert (
        client.patch(
            endpoint, json={"title": "Changed", "grant_number": other_grant["grant_number"]}
        ).status_code
        == 409
    )
    assert client.get(f"/api/stocks/{stock.id}/grants").get_json()[0] == saved
    other = Stock(family_id=stock.family_id, name="Other", symbol="OTHER")
    db.session.add(other)
    db.session.commit()
    assert (
        client.patch(
            f"/api/stocks/{other.id}/grants/{saved['id']}", json={"grant_date": "2020-01-01"}
        ).status_code
        == 404
    )

    def fail_update(*_):
        raise SQLAlchemyError("Simulated update failure")

    event.listen(StockGrant, "before_update", fail_update)
    try:
        assert client.patch(endpoint, json={"grant_date": "2020-01-01"}).status_code == 500
    finally:
        event.remove(StockGrant, "before_update", fail_update)
    assert client.get(f"/api/stocks/{stock.id}/grants").get_json()[0] == saved
    for archive_family in (False, True):
        stock.is_archived = not archive_family
        stock.family.is_archived = archive_family
        db.session.commit()
        assert client.patch(endpoint, json={"grant_date": "2020-01-01"}).status_code == 410
