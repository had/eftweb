from decimal import Decimal

from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.family.models import Family, FamilyMember
from app.stocks.import_parsers import parse_workbook
from app.stocks.models import Stock, StockSale
from tests import test_stock_import as import_fixtures
from tests.test_stock_import import add_lots, broker_file, broker_row, confirm, preview

app = import_fixtures.app
stock = import_fixtures.stock


def test_missing_fmv_requires_input_and_never_changes_quantity(app, stock):
    grant, _ = add_lots(stock)
    content = broker_file([broker_row(**{"Vest Date FMV": None})])
    client = app.test_client()
    view = preview(client, stock.id, content).get_json()
    assert not view["can_import"]
    assert confirm(client, stock.id, content, view).status_code == 400
    choices = {
        view["sales"][0]["key"]: {
            "reviewed": True,
            "allocations": [
                {
                    "vesting_id": grant.vestings[0].id,
                    "quantity": 286,
                    "acquisition_fmv": "99.123456",
                }
            ],
        }
    }
    response = confirm(client, stock.id, content, view, choices)
    assert response.status_code == 201, response.get_json()
    assert grant.vestings[0].acquisition_fmv == Decimal("99.123456")
    assert grant.vestings[0].quantity == 286


def test_order_fees_include_skipped_and_duplicate_executions(app, stock):
    grant, _ = add_lots(stock)
    rows = [
        broker_row(**{"Quantity": qty, "Proceeds Per Share": price, "Total Proceeds": qty * price})
        for qty, price in ((100, 120), (186, 130))
    ]
    content = broker_file(rows)
    client = app.test_client()
    view = preview(client, stock.id, content).get_json()
    first = next(s for s in view["sales"] if s["quantity"] == 100)
    second = next(s for s in view["sales"] if s["quantity"] == 186)
    choices = {
        first["key"]: {"skip": True, "order_fee": "9.99"},
        second["key"]: {"order_fee": "9.99"},
    }
    assert confirm(client, stock.id, content, view, choices).status_code == 201
    saved = StockSale.query.one()
    assert saved.quantity == 186 and saved.fees == Decimal("6.68")
    # Reimport the missing execution: duplicate execution keeps its share of the order fee.
    view = preview(client, stock.id, content).get_json()
    choices = {s["key"]: {"order_fee": "9.99", "reviewed": True} for s in view["sales"]}
    assert confirm(client, stock.id, content, view, choices).status_code == 201
    assert sum(s.fees for s in StockSale.query.all()) == Decimal("9.99")
    assert grant.vestings[0].quantity == 286


def test_conflicting_fmv_rejected_and_failed_commit_rolls_back_lot_values(app, stock):
    grant, _ = add_lots(stock)
    content = broker_file(
        [
            broker_row(**{"Quantity": 100, "Total Proceeds": 13044}),
            broker_row(**{"Quantity": 186, "Total Proceeds": 24261.84, "Vest Date FMV": 101}),
        ]
    )
    view = preview(app.test_client(), stock.id, content).get_json()
    assert not view["can_import"]
    assert any("conflicting acquisition FMV" in e for s in view["sales"] for e in s["errors"])
    content = broker_file()
    client = app.test_client()
    view = preview(client, stock.id, content).get_json()

    def fail(*args):
        raise SQLAlchemyError("test")

    event.listen(StockSale, "before_insert", fail)
    try:
        assert confirm(client, stock.id, content, view).status_code == 500
    finally:
        event.remove(StockSale, "before_insert", fail)
    assert grant.vestings[0].acquisition_fmv == 0 and StockSale.query.count() == 0


def test_invalid_skipped_execution_keeps_fee_share_and_manual_fmv_is_validated(app, stock):
    grant, _ = add_lots(stock)
    content = broker_file(
        [
            broker_row(
                **{
                    "Quantity": 100,
                    "Proceeds Per Share": 120,
                    "Total Proceeds": 12000,
                    "Vest Date FMV": "invalid",
                }
            ),
            broker_row(**{"Quantity": 186, "Proceeds Per Share": 130, "Total Proceeds": 24180}),
        ]
    )
    client = app.test_client()
    view = preview(client, stock.id, content).get_json()
    choices = {s["key"]: {"skip": bool(s["errors"]), "order_fee": "9.99"} for s in view["sales"]}
    assert confirm(client, stock.id, content, view, choices).status_code == 201
    assert StockSale.query.one().fees == Decimal("6.68")
    content = broker_file([broker_row(**{"Quantity": 1, "Order Number": "NEW"})])
    view = preview(client, stock.id, content).get_json()
    choices = {
        view["sales"][0]["key"]: {
            "reviewed": True,
            "allocations": [
                {"vesting_id": grant.vestings[0].id, "quantity": 1, "acquisition_fmv": "NaN"}
            ],
        }
    }
    assert confirm(client, stock.id, content, view, choices).status_code == 400
    assert StockSale.query.count() == 1


def test_espp_uses_acquisition_market_value_and_v3_roundtrips_tax_data(app, stock):
    grant, purchase = add_lots(stock)
    grant.approval_date = grant.grant_date
    grant.taxpayer_role = "taxpayer1"
    db.session.commit()
    rows = [
        broker_row(),
        broker_row(
            **{
                "Plan Type": "ESPP",
                "Order Type": "Sell ESPP",
                "Date Sold": "06/01/2026",
                "Quantity": 47,
                "Total Proceeds": 47 * 130.44,
                "Date Acquired": "05/15/2026",
                "Purchase Date": "05/15/2026",
                "Grant Number": "--",
                "Vest Date": "--",
                "Order Number": "ESPP-1",
                "Purchase Date Fair Mkt. Value": 75.123456,
            }
        ),
    ]
    content = broker_file(rows)
    client = app.test_client()
    view = preview(client, stock.id, content).get_json()
    assert confirm(client, stock.id, content, view).status_code == 201
    assert purchase.acquisition_fmv == Decimal("75.123456")
    raw = client.get(f"/api/stocks/{stock.id}/export").data
    parsed = parse_workbook(raw)
    assert parsed["version"] == 3
    assert parsed["grants"][0]["approval_date"] == grant.approval_date.isoformat()
    assert parsed["grants"][0]["taxpayer_role"] == "taxpayer1"
    assert parsed["purchases"][0]["acquisition_fmv"] == "75.123456"
    target = Stock(
        family=Family(
            members=[
                FamilyMember(
                    role="taxpayer1",
                    position=1,
                    first_name="Ada",
                    last_name="Example",
                    date_of_birth=grant.grant_date,
                )
            ]
        ),
        name="Restore",
        symbol="AAPL",
    )
    db.session.add(target)
    db.session.commit()
    view = preview(client, target.id, raw).get_json()
    assert confirm(client, target.id, raw, view).status_code == 201
    assert target.grants[0].approval_date == grant.approval_date
    assert target.purchases[0].acquisition_fmv == purchase.acquisition_fmv
