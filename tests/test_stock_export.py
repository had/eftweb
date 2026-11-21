from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import create_app, db
from app.api.stock_export import XLSX_MIME_TYPE
from app.constants import JAVASCRIPT_MAX_SAFE_INTEGER
from app.family.models import Family
from app.stocks.models import (
    GrantVesting,
    Stock,
    StockGrant,
    StockPurchase,
    StockSale,
    StockSaleAllocation,
)
from config import TestingConfig


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'export.sqlite'}"
    )
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def bookkeeping():
    return {"creation_token": str(uuid4()), "request_hash": "internal-request-hash"}


@pytest.fixture()
def stock(app):
    stock = Stock(family=Family(), name="Apple", symbol="AAPL")
    db.session.add(stock)
    db.session.commit()
    return stock


def add_records(stock):
    stock.grants = [
        StockGrant(
            title="Same name",
            grant_date=date(2020, 1, 1),
            quantity=160,
            vesting_start_date=date(2020, 2, 29),
            schedule_type="cliff-quarterly",
            customized=True,
            **bookkeeping(),
            vestings=[
                GrantVesting(date=date(2021, 1, 1), quantity=100),
                GrantVesting(date=date(2021, 1, 1), quantity=40),
                GrantVesting(date=date(2035, 1, 1), quantity=20),
            ],
        ),
        StockGrant(
            title="Same name",
            grant_date=date(2020, 1, 1),
            quantity=30,
            vesting_start_date=date(2020, 1, 1),
            schedule_type="quarterly",
            customized=False,
            **bookkeeping(),
            vestings=[GrantVesting(date=date(2022, 1, 1), quantity=30)],
        ),
    ]
    stock.purchases = [
        StockPurchase(
            purchase_date=date(2022, 1, 1), quantity=10, plan_name="ESPP", **bookkeeping()
        ),
        StockPurchase(
            purchase_date=date(2022, 7, 1), quantity=20, plan_name="Other plan", **bookkeeping()
        ),
    ]
    db.session.flush()
    first, second, _ = stock.grants[0].vestings
    stock.sales = [
        StockSale(
            transaction_date=date(2023, 1, 1),
            quantity=70,
            proceeds_per_share=Decimal("123.456789"),
            currency="USD",
            **bookkeeping(),
            allocations=[
                StockSaleAllocation(vesting_id=first.id, quantity=50),
                StockSaleAllocation(vesting_id=second.id, quantity=10),
                StockSaleAllocation(purchase_id=stock.purchases[0].id, quantity=10),
            ],
        ),
        StockSale(
            transaction_date=date(2024, 1, 1),
            quantity=15,
            proceeds_per_share=Decimal("99999999.999999"),
            currency="USD",
            **bookkeeping(),
            allocations=[
                StockSaleAllocation(vesting_id=first.id, quantity=5),
                StockSaleAllocation(purchase_id=stock.purchases[1].id, quantity=10),
            ],
        ),
    ]
    db.session.commit()


def export(client, stock_id):
    response = client.get(f"/api/stocks/{stock_id}/export")
    assert response.status_code == 200
    return load_workbook(BytesIO(response.data)), response


def table_rows(sheet, header_row):
    headers = [cell.value for cell in sheet[header_row]]
    return [
        dict(zip(headers, values, strict=True))
        for values in sheet.iter_rows(min_row=header_row + 1, values_only=True)
    ]


def test_empty_stock_has_metadata_two_sheets_and_download_headers(app, stock):
    workbook, response = export(app.test_client(), stock.id)
    assert response.mimetype == XLSX_MIME_TYPE
    assert response.headers["Content-Disposition"] == "attachment; filename=AAPL-export.xlsx"
    assert response.headers["Cache-Control"] == "no-store"
    assert workbook.sheetnames == ["Plans & vestings", "Sales"]
    plans = workbook.worksheets[0]
    assert list(plans.iter_rows(min_row=1, max_row=4, max_col=2, values_only=True)) == [
        ("export_format", "eftweb.stock"),
        ("schema_version", 3),
        ("stock_name", "Apple"),
        ("stock_symbol", "AAPL"),
    ]
    assert table_rows(plans, 6) == []
    assert table_rows(workbook["Sales"], 1) == []
    for sheet, freeze, header in ((plans, "A7", 6), (workbook["Sales"], "A2", 1)):
        assert sheet.freeze_panes == freeze
        assert sheet.auto_filter.ref.startswith(f"A{header}:")
        assert sheet.cell(header, 1).font.bold
        assert sheet.column_dimensions["A"].width >= 18


def test_complete_records_exact_values_links_and_deterministic_order(app, stock):
    add_records(stock)
    workbook, _ = export(app.test_client(), stock.id)
    plans = table_rows(workbook.worksheets[0], 6)
    assert [row["record_type"] for row in plans] == ["rsu_vesting"] * 4 + ["stock_purchase"] * 2
    assert len({row["grant_key"] for row in plans[:4]}) == 2
    assert [row["vesting_date"] for row in plans[:3]] == ["2021-01-01", "2021-01-01", "2035-01-01"]
    assert plans[0]["grant_quantity"] == 160
    assert plans[0]["customized"] is True
    assert plans[3]["customized"] is False
    assert plans[0]["vesting_start_date"] == "2020-02-29"
    assert plans[0]["schedule_type"] == "cliff-quarterly"
    assert plans[4]["plan_name"] == "ESPP"
    assert plans[5]["plan_name"] == "Other plan"
    sales = table_rows(workbook["Sales"], 1)
    assert len(sales) == 5
    assert [row["sale_quantity"] for row in sales] == [70, 70, 70, 15, 15]
    assert [row["allocation_quantity"] for row in sales] == [50, 10, 10, 5, 10]
    assert sales[0]["proceeds_per_share"] == "123.456789"
    assert sales[-1]["proceeds_per_share"] == "99999999.999999"
    assert {row["currency"] for row in sales} == {"USD"}
    assert sales[0]["vesting_key"] == sales[3]["vesting_key"] == plans[0]["vesting_key"]
    assert sales[1]["vesting_key"] == plans[1]["vesting_key"]
    assert sales[2]["purchase_key"] == plans[4]["purchase_key"]
    assert sales[4]["purchase_key"] == plans[5]["purchase_key"]
    again, _ = export(app.test_client(), stock.id)
    for first, second in zip(workbook, again, strict=True):
        assert list(first.values) == list(second.values)
    assert "internal-request-hash" not in str(list(workbook.worksheets[0].values))


def restore_workbook(workbook):
    """Test the interchange contract without introducing a production importer."""
    metadata = dict(workbook.worksheets[0].iter_rows(max_row=4, max_col=2, values_only=True))
    restored = Stock(family=Family(), name=metadata["stock_name"], symbol=metadata["stock_symbol"])
    db.session.add(restored)
    grants, vestings, purchases, sales = {}, {}, {}, {}
    for row in table_rows(workbook.worksheets[0], 6):
        if row["record_type"] == "stock_purchase":
            purchase = StockPurchase(
                stock=restored,
                plan_name=row["plan_name"],
                purchase_date=date.fromisoformat(row["purchase_date"]),
                quantity=int(row["purchase_quantity"]),
                **bookkeeping(),
            )
            purchases[row["purchase_key"]] = purchase
            db.session.add(purchase)
            continue
        key = row["grant_key"]
        if key not in grants:
            grant = StockGrant(
                stock=restored,
                title=row["plan_name"],
                grant_date=date.fromisoformat(row["grant_date"]),
                quantity=int(row["grant_quantity"]),
                vesting_start_date=date.fromisoformat(row["vesting_start_date"]),
                schedule_type=row["schedule_type"],
                customized=row["customized"],
                **bookkeeping(),
            )
            grants[key] = grant
            db.session.add(grant)
        if row["record_type"] == "rsu_vesting":
            vesting = GrantVesting(
                grant=grants[key],
                date=date.fromisoformat(row["vesting_date"]),
                quantity=int(row["vesting_quantity"]),
            )
            vestings[row["vesting_key"]] = vesting
            db.session.add(vesting)
    db.session.flush()
    for row in table_rows(workbook["Sales"], 1):
        key = row["sale_key"]
        if key not in sales:
            sale = StockSale(
                stock=restored,
                transaction_date=date.fromisoformat(row["transaction_date"]),
                quantity=int(row["sale_quantity"]),
                proceeds_per_share=Decimal(row["proceeds_per_share"]),
                currency=row["currency"],
                **bookkeeping(),
            )
            sales[key] = sale
            db.session.add(sale)
        if row["allocation_quantity"] is not None:
            source = (
                {"vesting_id": vestings[row["vesting_key"]].id}
                if row["vesting_key"]
                else {"purchase_id": purchases[row["purchase_key"]].id}
            )
            sales[key].allocations.append(
                StockSaleAllocation(**source, quantity=int(row["allocation_quantity"]))
            )
    db.session.commit()
    return restored


def test_workbook_reconstructs_same_records_and_balances_with_new_ids(app, stock):
    add_records(stock)
    workbook, _ = export(app.test_client(), stock.id)
    restored = restore_workbook(workbook)
    assert restored.id != stock.id
    assert (restored.name, restored.symbol) == (stock.name, stock.symbol)
    for original, copy in zip(stock.grants, restored.grants, strict=True):
        assert original.id != copy.id
        original_data, copy_data = original.to_dict(), copy.to_dict()
        for data in (original_data, copy_data):
            data.pop("id")
            data.pop("stock_id")
            for row in data["vestings"]:
                row.pop("id")
        assert original_data == copy_data
    for original, copy in zip(stock.purchases, restored.purchases, strict=True):
        assert original.id != copy.id
        assert (original.plan_name, original.purchase_date, original.quantity) == (
            copy.plan_name,
            copy.purchase_date,
            copy.quantity,
        )
    for original, copy in zip(stock.sales, restored.sales, strict=True):
        assert original.id != copy.id
        assert (
            original.transaction_date,
            original.quantity,
            original.proceeds_per_share,
            original.currency,
        ) == (copy.transaction_date, copy.quantity, copy.proceeds_per_share, copy.currency)

    def holdings(stock):
        balances = {
            ("vesting_id", vesting.id): [vesting.date, vesting.quantity]
            for grant in stock.grants
            for vesting in grant.vestings
        }
        balances.update(
            {
                ("purchase_id", purchase.id): [purchase.purchase_date, purchase.quantity]
                for purchase in stock.purchases
            }
        )
        for sale in stock.sales:
            for allocation in sale.allocations:
                source = (
                    ("vesting_id", allocation.vesting_id)
                    if allocation.vesting_id is not None
                    else ("purchase_id", allocation.purchase_id)
                )
                balances[source][1] -= allocation.quantity
        return list(balances.values())

    assert holdings(stock) == holdings(restored)
    assert (
        sum(quantity for acquired, quantity in holdings(restored) if acquired <= date(2026, 11, 4))
        == 115
    )
    assert sum(quantity for _, quantity in holdings(restored)) == 135


@pytest.mark.parametrize("price", ["0.000001", "100.000000", "99999999.999999"])
def test_large_quantities_literal_strings_and_exact_prices(app, stock, price):
    add_records(stock)
    stock.name = '=HYPERLINK("https://example.com", "name")'
    stock.grants[0].title = "=1+1"
    stock.grants[0].quantity = JAVASCRIPT_MAX_SAFE_INTEGER
    stock.grants[0].vestings[0].quantity = JAVASCRIPT_MAX_SAFE_INTEGER
    stock.purchases[0].plan_name = "#N/A"
    stock.purchases[0].quantity = 10**15
    stock.sales[0].quantity = JAVASCRIPT_MAX_SAFE_INTEGER
    next(
        allocation
        for allocation in stock.sales[0].allocations
        if allocation.vesting_id == stock.grants[0].vestings[0].id
    ).quantity = JAVASCRIPT_MAX_SAFE_INTEGER
    stock.sales[0].proceeds_per_share = Decimal(price)
    db.session.commit()
    workbook, _ = export(app.test_client(), stock.id)
    plans, sales = workbook.worksheets
    assert plans["B3"].value == stock.name
    assert plans["C7"].value == "=1+1"
    assert plans["C11"].value == "#N/A"
    assert plans["E7"].value == plans["K7"].value == str(JAVASCRIPT_MAX_SAFE_INTEGER)
    assert plans["N11"].value == str(10**15)
    assert sales["C2"].value == sales["H2"].value == str(JAVASCRIPT_MAX_SAFE_INTEGER)
    assert sales["D2"].value == price
    assert all(
        cell.data_type not in ("f", "e") for sheet in workbook for row in sheet for cell in row
    )


def test_grant_without_vestings_is_preserved(app, stock):
    add_records(stock)
    stock.grants.append(
        StockGrant(
            title="Empty grant",
            grant_date=date(2025, 1, 1),
            quantity=1,
            vesting_start_date=date(2025, 1, 1),
            schedule_type="quarterly",
            customized=True,
            **bookkeeping(),
        )
    )
    db.session.commit()
    workbook, _ = export(app.test_client(), stock.id)
    row = table_rows(workbook.worksheets[0], 6)[4]
    assert row["record_type"] == "rsu_grant"
    assert row["plan_name"] == "Empty grant"
    assert row["vesting_key"] is None


def test_export_is_scoped_and_filename_is_sanitized(app, stock):
    add_records(stock)
    other = Stock(family=Family(), name="Other", symbol="../../OTHER")
    db.session.add(other)
    db.session.commit()
    workbook, response = export(app.test_client(), other.id)
    assert response.headers["Content-Disposition"] == "attachment; filename=OTHER-export.xlsx"
    assert workbook.worksheets[0]["B3"].value == "Other"
    assert table_rows(workbook.worksheets[0], 6) == []
    assert table_rows(workbook["Sales"], 1) == []


def test_missing_and_archived_stock_and_family_return_json(app, stock):
    client = app.test_client()
    response = client.get("/api/stocks/99999/export")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Stock not found"}
    stock.is_archived = True
    db.session.commit()
    assert client.get(f"/api/stocks/{stock.id}/export").status_code == 410
    stock.is_archived = False
    stock.family.is_archived = True
    db.session.commit()
    response = client.get(f"/api/stocks/{stock.id}/export")
    assert response.status_code == 410
    assert response.get_json() == {"error": "Stock or family is archived"}


def test_generation_failure_is_logged_and_returns_json(app, stock, monkeypatch, caplog):
    def fail(snapshot):
        raise OSError("Workbook failed")

    monkeypatch.setattr("app.api.stock_export.build_stock_export", fail)
    response = app.test_client().get(f"/api/stocks/{stock.id}/export")
    assert response.status_code == 500
    assert response.get_json() == {"error": "Could not export the stock. Please try again."}
    assert "Could not export stock" in caplog.text
    assert "Workbook failed" in caplog.text


def test_export_uses_one_snapshot_during_a_concurrent_write(app, stock, monkeypatch):
    add_records(stock)
    engine = db.engine
    with engine.connect() as connection:
        connection.execute(text("PRAGMA journal_mode=WAL"))
    stock_id = stock.id
    original = StockGrant.to_dict
    written = False

    def write_purchase():
        with Session(engine) as session:
            session.add(
                StockPurchase(
                    stock_id=stock_id,
                    purchase_date=date(2025, 1, 1),
                    quantity=5,
                    plan_name="Concurrent purchase",
                    **bookkeeping(),
                )
            )
            session.commit()

    def serialize_and_write(grant):
        nonlocal written
        result = original(grant)
        if not written:
            written = True
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(write_purchase).result(timeout=5)
        return result

    monkeypatch.setattr(StockGrant, "to_dict", serialize_and_write)
    workbook, _ = export(app.test_client(), stock_id)
    assert written
    assert len(table_rows(workbook.worksheets[0], 6)) == 6
    next_workbook, _ = export(app.test_client(), stock_id)
    assert len(table_rows(next_workbook.worksheets[0], 6)) == 7
