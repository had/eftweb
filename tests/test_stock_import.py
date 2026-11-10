import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy.exc import SQLAlchemyError

from app import create_app, db
from app.api import stock_import
from app.family.models import Family
from app.stocks.import_parsers import BROKER_HEADERS, parse_workbook
from app.stocks.models import (
    GrantVesting,
    Stock,
    StockGrant,
    StockImportReceipt,
    StockPurchase,
    StockSale,
    StockSaleAllocation,
)
from config import TestingConfig


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'import.sqlite'}"
    )
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def stock(app):
    stock = Stock(family=Family(), name="Apple", symbol="AAPL")
    db.session.add(stock)
    db.session.commit()
    return stock


def bookkeeping():
    return {"creation_token": str(uuid4()), "request_hash": "hash"}


def add_lots(stock, number="20207560"):
    grant = StockGrant(
        stock=stock,
        title="Broker grant",
        grant_number=number,
        grant_date=date(2023, 12, 22),
        quantity=569,
        vesting_start_date=date(2023, 12, 1),
        schedule_type="quarterly",
        customized=True,
        **bookkeeping(),
        vestings=[
            GrantVesting(date=date(2025, 3, 1), quantity=286),
            GrantVesting(date=date(2025, 6, 1), quantity=283),
        ],
    )
    purchase = StockPurchase(
        stock=stock, plan_name="ESPP", purchase_date=date(2026, 5, 15), quantity=47, **bookkeeping()
    )
    db.session.add_all([grant, purchase])
    db.session.commit()
    return grant, purchase


def broker_row(**overrides):
    return {
        "Record Type": "Sell",
        "Symbol": "AAPL",
        "Plan Type": "RS",
        "Quantity": 286,
        "Date Acquired": "03/01/2025",
        "Date Sold": "02/12/2026",
        "Total Proceeds": 37305.84,
        "Proceeds Per Share": 130.44,
        "Order Type": "Sell Restricted Stock",
        "Grant Date": "12/22/2023",
        "Purchase Date": "--",
        "Grant Number": "20207560",
        "Vest Date": "03/01/2025",
        "Order Number": 99766164,
        **overrides,
    }


def workbook_bytes(workbook):
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def broker_file(rows=None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "G&L_Expanded"
    sheet.append(BROKER_HEADERS)
    for row in rows if rows is not None else [broker_row()]:
        sheet.append([row.get(header) for header in BROKER_HEADERS])
    return workbook_bytes(workbook)


def preview(client, stock_id, content):
    return client.post(
        f"/api/stocks/{stock_id}/import/preview", data={"file": (BytesIO(content), "data.xlsx")}
    )


def confirm(client, stock_id, content, review, decisions=None, token=None):
    return client.post(
        f"/api/stocks/{stock_id}/import",
        data={
            "file": (BytesIO(content), "data.xlsx"),
            "stock_revision": review["stock_revision"],
            "decisions": json.dumps(decisions or {}),
        },
        headers={"Idempotency-Key": token or str(uuid4())},
    )


def test_broker_preview_commit_duplicates_receipt_and_provenance(app, stock):
    grant, _ = add_lots(stock)
    content = broker_file()
    client = app.test_client()
    review = preview(client, stock.id, content).get_json()
    assert review["format"] == "etrade"
    assert review["can_import"]
    sale = review["sales"][0]
    assert sale["allocations"] == [{"vesting_id": grant.vestings[0].id, "quantity": 286}]
    assert StockSale.query.count() == StockImportReceipt.query.count() == 0
    key = str(uuid4())
    saved = confirm(client, stock.id, content, review, token=key)
    assert saved.status_code == 201
    assert saved.get_json()["counts"]["sales"] == 1
    again = confirm(client, stock.id, content, review, token=key)
    assert again.status_code == 200
    assert again.get_json() == saved.get_json()
    assert (
        confirm(
            client, stock.id, content, review, decisions={sale["key"]: {"skip": True}}, token=key
        ).status_code
        == 409
    )
    duplicate = preview(client, stock.id, content).get_json()
    assert duplicate["sales"][0]["status"] == "duplicate"
    assert duplicate["sales"][0]["skip"]
    assert confirm(client, stock.id, content, duplicate).status_code == 201
    assert StockSale.query.count() == 1
    db.session.expire_all()
    saved_sale = StockSale.query.one()
    assert saved_sale.import_source == "etrade"
    assert saved_sale.source_order_number == "99766164"
    assert saved_sale.source_fingerprint == sale["source_fingerprint"]


def test_splits_combine_ignore_stc_and_different_prices_stay_separate(app, stock):
    add_lots(stock)
    rows = [
        {"Record Type": "Summary", "Quantity": 623},
        broker_row(),
        *[
            broker_row(
                **{
                    "Order Number": 100617036,
                    "Date Sold": "03/12/2026",
                    "Quantity": quantity,
                    "Proceeds Per Share": 130,
                    "Total Proceeds": quantity * 130,
                    "Date Acquired": "06/01/2025",
                    "Vest Date": "06/01/2025",
                }
            )
            for quantity in (1, 10, 272)
        ],
        broker_row(
            **{
                "Order Type": "ESPP STC",
                "Plan Type": "ESPP",
                "Quantity": 7,
                "Proceeds Per Share": "=1+1",
            }
        ),
        broker_row(
            **{
                "Plan Type": "ESPP",
                "Order Type": "Sell ESPP",
                "Date Sold": "06/01/2026",
                "Quantity": 47,
                "Proceeds Per Share": 276.214255,
                "Total Proceeds": 12982.069985,
                "Date Acquired": "05/15/2026",
                "Purchase Date": "05/15/2026",
                "Grant Date": "11/17/2025",
                "Grant Number": "--",
                "Vest Date": "--",
                "Order Number": 103526494,
            }
        ),
    ]
    content = broker_file(rows)
    review = preview(app.test_client(), stock.id, content).get_json()
    assert review["can_import"]
    assert [sale["quantity"] for sale in review["sales"]] == [286, 283, 47]
    assert len(review["sales"][1]["allocations"]) == 1
    assert len(review["ignored"]) == 2
    assert confirm(app.test_client(), stock.id, content, review).status_code == 201
    assert StockSale.query.count() == 3
    assert StockSaleAllocation.query.count() == 3
    assert StockSale.query.order_by(
        StockSale.transaction_date.desc()
    ).first().proceeds_per_share == Decimal("276.214255")
    # A different execution price within an order remains a separate sale proposal.
    split = parse_workbook(
        broker_file(
            [
                broker_row(**{"Quantity": 1, "Total Proceeds": 130.44}),
                broker_row(**{"Quantity": 2, "Proceeds Per Share": 131, "Total Proceeds": 262}),
            ]
        )
    )
    assert len(split["sales"]) == 2


def test_missing_ambiguous_lots_manual_splits_and_review(app, stock):
    grant, _ = add_lots(stock, number=None)
    # Split a broker lot across two manually recorded releases on the same day.
    grant.vestings[0].quantity = 200
    grant.vestings.append(GrantVesting(date=date(2025, 3, 1), quantity=86))
    db.session.commit()
    content = broker_file()
    client = app.test_client()
    review = preview(client, stock.id, content).get_json()
    assert not review["can_import"]
    sale = review["sales"][0]
    assert sale["matching_issues"]
    decision = {
        sale["key"]: {
            "allocations": [
                {"vesting_id": grant.vestings[0].id, "quantity": 200},
                {"vesting_id": grant.vestings[-1].id, "quantity": 86},
            ]
        }
    }
    assert confirm(client, stock.id, content, review, decision).status_code == 400
    decision[sale["key"]]["reviewed"] = True
    assert confirm(client, stock.id, content, review, decision).status_code == 201
    assert StockSaleAllocation.query.count() == 2
    db.session.expire_all()
    assert grant.grant_number is None  # Import mappings never mutate grant metadata.


def test_manual_duplicate_requires_explicit_review_or_skip(app, stock):
    grant, _ = add_lots(stock)
    db.session.add(
        StockSale(
            stock=stock,
            transaction_date=date(2026, 2, 12),
            quantity=286,
            proceeds_per_share=Decimal("130.44"),
            currency="USD",
            **bookkeeping(),
        )
    )
    # Sale-only records are legal in the native schema and still need duplicate review.
    db.session.commit()
    content = broker_file()
    client = app.test_client()
    review = preview(client, stock.id, content).get_json()
    sale = review["sales"][0]
    assert sale["possible_duplicate_ids"]
    assert confirm(client, stock.id, content, review).status_code == 400
    assert (
        confirm(client, stock.id, content, review, {sale["key"]: {"skip": True}}).status_code == 201
    )
    assert StockSale.query.count() == 1
    review = preview(client, stock.id, content).get_json()
    assert (
        confirm(client, stock.id, content, review, {sale["key"]: {"reviewed": True}}).status_code
        == 201
    )
    assert StockSale.query.count() == 2


def test_changed_broker_order_is_a_conflict_and_can_only_be_skipped(app, stock):
    add_lots(stock)
    client = app.test_client()
    content = broker_file([broker_row(**{"Quantity": 20, "Total Proceeds": 2608.8})])
    review = preview(client, stock.id, content).get_json()
    assert confirm(client, stock.id, content, review).status_code == 201
    changed = broker_file([broker_row(**{"Quantity": 21, "Total Proceeds": 2739.24})])
    review = preview(client, stock.id, changed).get_json()
    sale = review["sales"][0]
    assert sale["status"] == "conflict"
    assert (
        confirm(client, stock.id, changed, review, {sale["key"]: {"reviewed": True}}).status_code
        == 400
    )
    assert (
        confirm(client, stock.id, changed, review, {sale["key"]: {"skip": True}}).status_code == 201
    )
    assert StockSale.query.one().quantity == 20


def test_batch_availability_counts_all_selected_sales_and_existing_sales(app, stock):
    add_lots(stock)
    client = app.test_client()
    content = broker_file(
        [
            broker_row(**{"Quantity": 200, "Order Number": order, "Total Proceeds": 26088})
            for order in (1, 2)
        ]
    )
    review = preview(client, stock.id, content).get_json()
    assert not review["can_import"]
    assert confirm(client, stock.id, content, review).status_code == 400
    assert StockSale.query.count() == 0
    decision = {review["sales"][1]["key"]: {"skip": True}}
    assert confirm(client, stock.id, content, review, decision).status_code == 201
    another = broker_file(
        [broker_row(**{"Quantity": 100, "Order Number": 3, "Total Proceeds": 13044})]
    )
    review = preview(client, stock.id, another).get_json()
    assert not review["can_import"]


def test_stale_preview_and_failed_commit_leave_no_partial_records(app, stock, monkeypatch):
    add_lots(stock)
    client = app.test_client()
    content = broker_file()
    review = preview(client, stock.id, content).get_json()
    stock.name = "Renamed"
    db.session.commit()
    assert confirm(client, stock.id, content, review).status_code == 409
    fresh = preview(client, stock.id, content).get_json()
    persist_import = stock_import.persist_import

    def fail(*args):
        persist_import(*args)
        db.session.flush()
        raise SQLAlchemyError("Simulated failure")

    monkeypatch.setattr("app.api.stock_import.persist_import", fail)
    assert confirm(client, stock.id, content, fresh).status_code == 500
    assert (
        StockSale.query.count()
        == StockSaleAllocation.query.count()
        == StockImportReceipt.query.count()
        == 0
    )


def test_concurrent_confirmations_serialize_and_same_token_replays(app, stock):
    add_lots(stock)
    stock_id = stock.id
    content = broker_file()
    review = preview(app.test_client(), stock_id, content).get_json()
    token = str(uuid4())

    def write():
        return confirm(app.test_client(), stock_id, content, review, token=token).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: write(), range(2))) == [200, 201]
    assert StockSale.query.count() == StockImportReceipt.query.count() == 1


def test_grant_number_creation_edit_validation_uniqueness_and_old_retry(app, stock):
    grant, _ = add_lots(stock, number="000123")
    client = app.test_client()
    endpoint = f"/api/stocks/{stock.id}/grants/{grant.id}"
    assert (
        client.patch(endpoint, json={"grant_number": "001234"}).get_json()["grant_number"]
        == "001234"
    )
    assert client.patch(endpoint, json={"grant_number": 123}).status_code == 400
    assert client.patch(endpoint, json={"grant_number": "1", "title": "wrong"}).status_code == 400
    assert client.patch(endpoint, json={"grant_number": None}).status_code == 200
    payload = {
        "title": "New",
        "grant_date": "2020-01-01",
        "quantity": 1,
        "vesting_start_date": "2020-01-01",
        "schedule_type": "quarterly",
        "customized": True,
        "vestings": [{"date": "2021-01-01", "quantity": 1}],
    }
    token = str(uuid4())
    headers = {"Idempotency-Key": token}
    first = client.post(f"/api/stocks/{stock.id}/grants", json=payload, headers=headers)
    assert first.status_code == 201
    assert (
        client.post(
            f"/api/stocks/{stock.id}/grants",
            json={**payload, "grant_number": None},
            headers=headers,
        ).status_code
        == 200
    )
    second = client.post(
        f"/api/stocks/{stock.id}/grants",
        json={**payload, "grant_number": "001234"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert second.status_code == 201
    assert client.patch(endpoint, json={"grant_number": "001234"}).status_code == 409
    assert (
        client.post(
            f"/api/stocks/{stock.id}/grants",
            json={**payload, "grant_number": "001234"},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 409
    )
    other = Stock(family=Family(), name="Other", symbol="AAPL")
    db.session.add(other)
    db.session.commit()
    assert (
        client.patch(
            f"/api/stocks/{other.id}/grants/{grant.id}", json={"grant_number": "x"}
        ).status_code
        == 404
    )


def test_native_v2_roundtrip_restores_provenance_and_rejects_nonempty_targets(app, stock):
    grant, _ = add_lots(stock)
    client = app.test_client()
    content = broker_file()
    assert (
        confirm(
            client, stock.id, content, preview(client, stock.id, content).get_json()
        ).status_code
        == 201
    )
    native = client.get(f"/api/stocks/{stock.id}/export").data
    parsed = parse_workbook(native)
    assert parsed["version"] == 2
    assert parsed["grants"][0]["grant_number"] == "20207560"
    target = Stock(family=Family(), name="Different name", symbol="AAPL")
    db.session.add(target)
    db.session.commit()
    target_id = target.id
    review = preview(client, target_id, native).get_json()
    assert review["can_import"]
    assert confirm(client, target_id, native, review).status_code == 201
    db.session.expire_all()
    assert target.name == stock.name
    assert target.grants[0].id != grant.id
    assert target.grants[0].grant_number == "20207560"
    assert target.sales[0].source_fingerprint == stock.sales[0].source_fingerprint
    assert target.sales[0].allocations[0].vesting_id == target.grants[0].vestings[0].id
    assert preview(client, target_id, content).get_json()["sales"][0]["status"] == "duplicate"
    assert not preview(client, target_id, native).get_json()["can_import"]
    assert (
        confirm(
            client, target_id, native, preview(client, target_id, native).get_json()
        ).status_code
        == 400
    )


@pytest.mark.parametrize("filename", ["AAPL-export.xlsx", "sample_etrade.xlsx"])
def test_supplied_reference_workbooks(app, stock, filename):
    path = Path(__file__).resolve().parents[2] / filename
    if not path.exists():
        pytest.skip(
            "Local user reference workbook is unavailable; generated fixtures cover the same formats"
        )
    content = path.read_bytes()
    client = app.test_client()
    if filename == "sample_etrade.xlsx":
        assert not preview(client, stock.id, content).get_json()["can_import"]
        add_lots(stock)
    review = preview(client, stock.id, content).get_json()
    assert review["can_import"]
    if filename == "AAPL-export.xlsx":
        assert review["counts"] == {"grants": 2, "purchases": 1, "sales": 1}
        assert sum(len(grant["vestings"]) for grant in review["grants"]) == 24
        assert [row["quantity"] for row in review["sales"][0]["allocations"]] == [138, 12]
    else:
        assert [sale["quantity"] for sale in review["sales"]] == [286, 283, 47]
    assert confirm(client, stock.id, content, review).status_code == 201
    db.session.expire_all()
    assert len(stock.sales) == (1 if filename == "AAPL-export.xlsx" else 3)


@pytest.mark.parametrize(
    "changes",
    [
        {"Quantity": 1.5},
        {"Proceeds Per Share": 1.0000001},
        {"Order Type": "Unknown"},
        {"Plan Type": "OPTION"},
        {"Date Sold": "12/31/2099"},
        {"Grant Number": 10**16},
    ],
)
def test_unsupported_broker_sales_are_visible_and_skippable(app, stock, changes):
    add_lots(stock)
    content = broker_file([broker_row(**changes)])
    client = app.test_client()
    review = preview(client, stock.id, content).get_json()
    sale = review["sales"][0]
    assert sale["status"] == "invalid"
    assert not review["can_import"]
    assert (
        confirm(client, stock.id, content, review, {sale["key"]: {"skip": True}}).status_code == 201
    )
    assert StockSale.query.count() == 0


def test_warnings_native_excel_dates_and_malformed_inputs(app, stock):
    add_lots(stock)
    client = app.test_client()
    content = broker_file(
        [
            broker_row(
                **{"Date Sold": date(2026, 2, 12), "Grant Date": "12/21/2023", "Total Proceeds": 1}
            )
        ]
    )
    review = preview(client, stock.id, content).get_json()
    sale = review["sales"][0]
    assert sale["warnings"] and sale["matching_issues"]
    assert (
        confirm(client, stock.id, content, review, {sale["key"]: {"reviewed": True}}).status_code
        == 201
    )
    assert (
        preview(
            client, stock.id, broker_file([broker_row(), broker_row(**{"Symbol": "MSFT"})])
        ).status_code
        == 400
    )
    assert (
        preview(
            client, stock.id, broker_file([broker_row(**{"Proceeds Per Share": "=1+1"})])
        ).status_code
        == 400
    )
    assert preview(client, stock.id, b"not a zip").status_code == 400
    assert preview(client, 99999, broker_file()).status_code == 404
    stock.is_archived = True
    db.session.commit()
    assert preview(client, stock.id, broker_file()).status_code == 410


def test_workbook_limits_and_native_reference_validation(app, stock, monkeypatch):
    client = app.test_client()
    native = client.get(f"/api/stocks/{stock.id}/export").data
    workbook = load_workbook(BytesIO(native))
    workbook.worksheets[0]["B2"] = 99
    assert preview(client, stock.id, workbook_bytes(workbook)).status_code == 400
    workbook.worksheets[0]["B2"] = 2
    workbook["Sales"].append(["sale:x", "2026-01-01", 1, "1.000000", "USD", "unknown", None, 1])
    assert preview(client, stock.id, workbook_bytes(workbook)).status_code == 400
    monkeypatch.setattr("app.stocks.import_parsers.MAX_EXPANDED", 1)
    assert preview(client, stock.id, broker_file()).status_code == 400
    monkeypatch.undo()
    assert preview(client, stock.id, b"x" * (10 * 1024 * 1024 + 1)).status_code in (400, 413)
    workbook = Workbook()
    workbook.active.cell(100_011, 1, "too many rows")
    assert preview(client, stock.id, workbook_bytes(workbook)).status_code == 400


def test_native_orphan_forms_are_preserved(app, stock):
    grant = StockGrant(
        stock=stock,
        title="No schedule",
        grant_date=date(2020, 1, 1),
        quantity=1,
        vesting_start_date=date(2020, 1, 1),
        schedule_type="quarterly",
        customized=True,
        **bookkeeping(),
    )
    sale = StockSale(
        stock=stock,
        transaction_date=date(2021, 1, 1),
        quantity=1,
        proceeds_per_share=Decimal("1"),
        currency="USD",
        **bookkeeping(),
    )
    db.session.add_all([grant, sale])
    db.session.commit()
    native = app.test_client().get(f"/api/stocks/{stock.id}/export").data
    parsed = parse_workbook(native)
    assert parsed["grants"][0]["vestings"] == []
    assert parsed["sales"][0]["allocations"] == []
