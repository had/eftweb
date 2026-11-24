from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from requests import ConnectionError
from sqlalchemy import event

from app import create_app, db
from app.family.models import (
    CapitalGainHelperLine,
    CapitalGainStatement,
    Family,
    FamilyMember,
    FxCoverage,
    StockTaxReceipt,
    TaxReturn,
    UsdEurRate,
)
from app.service import stock_fx
from app.service.stock_fx import FxResolver, parse_ecb
from app.service.stock_tax import prepare, regime
from app.stocks.models import (
    GrantVesting,
    Stock,
    StockGrant,
    StockPurchase,
    StockSale,
    StockSaleAllocation,
)
from config import TestingConfig


def bookkeeping():
    return {"creation_token": str(uuid4()), "request_hash": "test"}


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'stock-tax.sqlite'}"
    )
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def context(app):
    family = Family(
        members=[
            FamilyMember(
                role=role,
                position=1,
                first_name=role,
                last_name="Test",
                date_of_birth=date(1980, 1, 1),
            )
            for role in ("taxpayer1", "taxpayer2")
        ]
    )
    tax_return = TaxReturn(family=family, year=2025, has_stock_statements=True)
    db.session.add(tax_return)
    db.session.commit()
    return tax_return


def sale(
    tax_return,
    symbol="ABC",
    quantity=10,
    fmv="100",
    price="110",
    acquired=date(2020, 1, 1),
    sold=date(2024, 1, 10),
    approval=date(2019, 1, 1),
    role="taxpayer1",
    fees="0",
    espp=False,
):
    stock = Stock.query.filter_by(family_id=tax_return.family_id, symbol=symbol).first()
    if stock is None:
        stock = Stock(family=tax_return.family, name=symbol, symbol=symbol)
        db.session.add(stock)
    if espp:
        lot = StockPurchase(
            stock=stock,
            purchase_date=acquired,
            quantity=quantity,
            acquisition_fmv=Decimal(fmv),
            **bookkeeping(),
        )
    else:
        grant = StockGrant(
            stock=stock,
            title="Grant",
            grant_date=acquired,
            approval_date=approval,
            taxpayer_role=role,
            quantity=quantity,
            vesting_start_date=acquired,
            schedule_type="quarterly",
            customized=True,
            **bookkeeping(),
        )
        lot = GrantVesting(
            grant=grant, date=acquired, quantity=quantity, acquisition_fmv=Decimal(fmv)
        )
        db.session.add(grant)
    db.session.add(lot)
    db.session.flush()
    source = {"purchase_id" if espp else "vesting_id": lot.id}
    item = StockSale(
        stock=stock,
        transaction_date=sold,
        quantity=quantity,
        proceeds_per_share=Decimal(price),
        fees=Decimal(fees),
        currency="USD",
        allocations=[StockSaleAllocation(**source, quantity=quantity)],
        **bookkeeping(),
    )
    db.session.add(item)
    db.session.commit()
    return item, lot


def overrides(*days):
    return {day.isoformat(): "1" for day in (date(2020, 1, 1), date(2024, 1, 10), *days)}


def preview(client, tax_return, rates=None):
    return client.post(
        f"/api/tax-returns/{tax_return.id}/stock-tax/preview",
        json={"fx_overrides": rates or overrides()},
    )


def accept(client, tax_return, view, **data):
    return client.post(
        f"/api/tax-returns/{tax_return.id}/stock-tax/accept",
        json={"source_revision": view["source_revision"], "fx_overrides": overrides(), **data},
        headers={"Idempotency-Key": str(uuid4())},
    )


@pytest.mark.parametrize(
    "day,expected",
    [
        (date(2015, 8, 8), "Macron I"),
        (date(2016, 12, 30), "Macron I"),
        (date(2016, 12, 31), "Macron II"),
        (date(2017, 1, 1), "Macron II"),
        (date(2017, 12, 31), "Macron II"),
        (date(2018, 1, 1), "Macron III"),
    ],
)
def test_boundaries(day, expected):
    assert regime(day) == expected


@pytest.mark.parametrize("day", [None, date(2015, 8, 7), date(2012, 9, 28)])
def test_unsupported_regimes(day):
    with pytest.raises(ValueError):
        regime(day)


def test_full_workflow_snapshots_edits_aggregation_replacement_and_removal(app, context):
    item, lot = sale(context)
    client = app.test_client()
    base = f"/api/tax-returns/{context.id}"
    manual = client.post(
        base + "/capital-gain-statements", json={"title": "Other broker", "capital_result": "-30"}
    )
    assert manual.status_code == 201
    view = preview(client, context).get_json()
    assert view["can_accept"] and view["income_year"] == 2024
    assert CapitalGainStatement.query.count() == 1
    assert CapitalGainHelperLine.query.count() == 0
    assert view["aggregate"]["3VG"] == "70"
    # A preview has no effect on the estimate until its statements are accepted.
    assert client.get(base + "/estimation").get_json()["tax_result"]["capital_gain_3VG"] == 0
    response = accept(client, context, view)
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["aggregate"]["3VG"] == "70"
    estimated = client.get(base + "/estimation").get_json()["tax_result"]
    assert estimated["capital_gain_3VG"] == 70
    assert estimated["taxable_acquisition_gain_1TZ"] == 500
    assert estimated["acquisition_gain_50p_rebates_1WZ"] == 500
    stock_statement = next(s for s in response.get_json()["statements"] if s["stock_id"])
    detail_url = base + f"/capital-gain-statements/{stock_statement['id']}"
    detail = client.get(detail_url).get_json()
    assert detail["lines"][0]["fields"]["515"] == "10"
    assert detail["lines"][0]["fields"]["520"] == "100.000000"
    lot.acquisition_fmv = 999
    item.proceeds_per_share = 1000
    db.session.commit()
    assert client.get(detail_url).get_json()["lines"] == detail["lines"]
    edited = client.put(detail_url, json={"reported": {"capital_result": "80"}})
    assert edited.status_code == 200
    assert edited.get_json()["computed"]["capital_result"] == "100"
    assert client.get(base + "/capital-gain-statements").get_json()["aggregate"]["3VG"] == "50"
    assert client.get(base + "/estimation").get_json()["tax_result"]["capital_gain_3VG"] == 50
    view = preview(client, context).get_json()
    assert accept(client, context, view).status_code == 409
    assert accept(client, context, view, replace_existing=True).status_code == 201
    assert CapitalGainStatement.query.count() == 2
    assert client.delete(f"/api/stocks/{item.stock_id}/sales").status_code == 204
    assert CapitalGainHelperLine.query.count() == 1
    view = preview(client, context).get_json()
    assert not view["statements"] and len(view["replacements"]) == 1
    assert accept(client, context, view, replace_existing=True).status_code == 201
    assert CapitalGainHelperLine.query.count() == 0
    assert client.get(base + "/capital-gain-statements").get_json()["aggregate"]["3VH"] == "30"


def test_stale_preview_and_idempotent_acceptance(app, context):
    item, lot = sale(context)
    client = app.test_client()
    view = preview(client, context).get_json()
    lot.acquisition_fmv = 101
    db.session.commit()
    assert accept(client, context, view).status_code == 409
    view = preview(client, context).get_json()
    body = {"source_revision": view["source_revision"], "fx_overrides": overrides()}
    url = f"/api/tax-returns/{context.id}/stock-tax/accept"
    headers = {"Idempotency-Key": str(uuid4())}
    first = client.post(url, json=body, headers=headers)
    again = client.post(url, json=body, headers=headers)
    assert first.status_code == 201 and again.status_code == 200
    assert first.get_json() == again.get_json()
    assert CapitalGainStatement.query.count() == 1
    assert (
        client.post(url, json={**body, "replace_existing": True}, headers=headers).status_code
        == 409
    )


def test_grant_edits_preserve_saved_helpers_and_invalidate_pending_preparation(app, context):
    item, lot = sale(context)
    client = app.test_client()
    original = accept(client, context, preview(client, context).get_json()).get_json()
    statement_id = original["statements"][0]["id"]
    detail_url = f"/api/tax-returns/{context.id}/capital-gain-statements/{statement_id}"
    saved_helper = client.get(detail_url).get_json()["lines"]
    pending = preview(client, context).get_json()
    allocations = item.to_dict()["allocations"]
    response = client.patch(
        f"/api/stocks/{item.stock_id}/grants/{lot.grant_id}",
        json={
            "grant_date": "2017-01-01",
            "approval_date": "2016-12-31",
            "taxpayer_role": "taxpayer2",
        },
    )
    assert response.status_code == 200
    assert item.to_dict()["allocations"] == allocations
    assert client.get(detail_url).get_json()["lines"] == saved_helper
    assert accept(client, context, pending, replace_existing=True).status_code == 409
    updated = preview(client, context).get_json()["statements"][0]["lines"][0]
    assert updated["regime"] == "Macron II"
    assert updated["taxpayer_role"] == "taxpayer2"


def test_threshold_across_stocks_taxpayers_order_and_crossing(app, context):
    sale(context, symbol="AAA", quantity=2000, price="100")
    sale(context, symbol="BBB", quantity=2000, price="100")
    sale(context, symbol="CCC", quantity=2000, price="100", role="taxpayer2")
    view = prepare(context, overrides())
    a, b, c = view["statements"]
    assert a["computed"]["1TZ"] == "100000" and a["computed"]["1TT"] == "0"
    assert b["computed"]["1TZ"] == "50000" and b["computed"]["1TT"] == "100000"
    assert b["lines"][0]["threshold_eligible"] == "100000.000000"
    assert c["computed"]["1TZ"] == "100000" and c["computed"]["1UT"] == "0"
    assert Decimal(view["threshold"]["taxpayer1"]["remaining"]) == 0
    assert Decimal(view["threshold"]["taxpayer2"]["remaining"]) == 100000


@pytest.mark.parametrize("quantity", [2999, 3000, 3001])
def test_threshold_edges(app, context, quantity):
    sale(context, quantity=quantity, price="100")
    values = prepare(context, overrides())["statements"][0]["computed"]
    assert values["1TT"] == str(max(0, quantity - 3000) * 100)
    assert values["1TZ"] == str(min(quantity, 3000) * 50)


@pytest.mark.parametrize(
    "acquired,rebate",
    [
        (date(2022, 1, 10), "500"),
        (date(2022, 1, 11), "0"),
        (date(2016, 1, 10), "650"),
        (date(2016, 1, 11), "500"),
    ],
)
def test_holding_period_boundaries_and_macron_one_exemption(app, context, acquired, rebate):
    sale(context, acquired=acquired, approval=date(2016, 1, 1))
    view = prepare(context, overrides(acquired))
    assert view["statements"][0]["computed"]["1UZ"] == rebate
    assert Decimal(view["threshold"]["taxpayer1"]["used"]) == 0


@pytest.mark.parametrize("espp,capital,acquisition", [(False, "0", "400"), (True, "-200", "0")])
def test_losses_are_not_counted_twice(app, context, espp, capital, acquisition):
    sale(context, price="80", espp=espp)
    statement = prepare(context, overrides())["statements"][0]
    assert statement["computed"]["capital_result"] == capital
    assert statement["computed"]["1TZ"] == acquisition
    assert statement["lines"][0]["fields"]["524"] == "-200"


def test_precision_rounding_fees_and_partial_allocations(app, context):
    item, lot = sale(context, quantity=1000, fmv="100.0049", price="110", fees="0", espp=True)
    assert prepare(context, overrides())["statements"][0]["computed"]["capital_result"] == "9995"
    item.quantity = 10
    item.allocations[0].quantity = 10
    item.fees = Decimal("3.25")
    db.session.commit()
    line = prepare(context, overrides())["statements"][0]["lines"][0]
    assert line["fields"]["515"] == "10" and line["fields"]["517"] == "3"
    assert line["fees_usd"] == "3.25"


def test_missing_inputs_block_and_archived_stocks_are_included(app, context):
    item, lot = sale(context, fmv="0")
    view = prepare(context, overrides())
    assert not view["can_accept"] and "Missing acquisition FMV" in view["errors"][0]
    lot.acquisition_fmv = 100
    lot.grant.approval_date = None
    db.session.commit()
    assert not prepare(context, overrides())["can_accept"]
    lot.grant.approval_date = date(2019, 1, 1)
    lot.grant.taxpayer_role = None
    db.session.commit()
    assert not prepare(context, overrides())["can_accept"]
    lot.grant.taxpayer_role = "taxpayer1"
    item.stock.is_archived = True
    db.session.commit()
    assert prepare(context, overrides())["can_accept"]


def test_failure_rolls_back_replacements(app, context):
    sale(context)
    client = app.test_client()
    assert accept(client, context, preview(client, context).get_json()).status_code == 201
    view = preview(client, context).get_json()

    def fail(*args):
        from sqlalchemy.exc import SQLAlchemyError

        raise SQLAlchemyError("test failure")

    event.listen(CapitalGainHelperLine, "before_insert", fail)
    try:
        assert accept(client, context, view, replace_existing=True).status_code == 500
    finally:
        event.remove(CapitalGainHelperLine, "before_insert", fail)
    assert CapitalGainStatement.query.count() == CapitalGainHelperLine.query.count() == 1
    assert StockTaxReceipt.query.count() == 1


def test_return_isolation_and_archive_rules(app, context):
    sale(context)
    client = app.test_client()
    statement = accept(client, context, preview(client, context).get_json()).get_json()[
        "statements"
    ][0]
    other = TaxReturn(family=Family(), year=2025, has_stock_statements=True)
    db.session.add(other)
    db.session.commit()
    assert (
        client.get(
            f"/api/tax-returns/{other.id}/capital-gain-statements/{statement['id']}"
        ).status_code
        == 404
    )
    context.is_archived = True
    db.session.commit()
    assert preview(client, context).status_code == 410


def test_fx_parsing_direction_coverage_lookback_and_override(app, monkeypatch):
    xml = b'<Envelope><Cube><Cube time="2024-01-05"><Cube currency="USD" rate="1.25"/></Cube></Cube></Envelope>'
    assert parse_ecb(xml) == {date(2024, 1, 5): Decimal("1.25")}
    db.session.add(UsdEurRate(date=date(2024, 1, 5), usd_per_eur=Decimal("1.25"), source="ECB"))
    db.session.add(FxCoverage(id=1, first_date=date(2024, 1, 5), last_date=date(2024, 1, 20)))
    db.session.commit()
    resolver = FxResolver([date(2024, 1, 7)], refresh=False)
    assert resolver.resolve(date(2024, 1, 7))[0] == Decimal("0.8")
    assert resolver.resolve(date(2024, 1, 12))[0] == Decimal("0.8")
    with pytest.raises(ValueError):
        resolver.resolve(date(2024, 1, 13))
    with pytest.raises(ValueError):
        resolver.resolve(date(2024, 1, 4))
    manual = FxResolver([date(2023, 1, 1)], {"2023-01-01": "0.9"})
    assert manual.resolve(date(2023, 1, 1))[0] == Decimal("0.9")
    assert UsdEurRate.query.count() == 1
    monkeypatch.setattr(
        stock_fx.requests, "get", lambda *a, **kw: (_ for _ in ()).throw(ConnectionError())
    )
    # A refresh failure does not invalidate still-covered dates.
    resolver = FxResolver([date(2024, 1, 7), date(2024, 1, 22)])
    assert resolver.resolve(date(2024, 1, 7))[0] == Decimal("0.8")
    with pytest.raises(ValueError):
        resolver.resolve(date(2024, 1, 22))


def test_acquisition_and_sale_rates_are_distinct(app, context):
    sale(context)
    view = prepare(context, {"2020-01-01": "0.8", "2024-01-10": "0.9"})
    line = view["statements"][0]["lines"][0]
    assert Decimal(line["fields"]["520"]) == 80
    assert Decimal(line["fields"]["514"]) == 99
    assert view["statements"][0]["computed"]["capital_result"] == "190"


def test_multiple_rsu_and_espp_lots_remain_distinct_with_exact_fees(app, context):
    first, lot1 = sale(context, quantity=3, price="150", fees="0.05")
    second, lot2 = sale(context, quantity=7, fmv="110", price="150")
    third, purchase = sale(context, quantity=5, fmv="120", price="150", espp=True)
    first.quantity = 15
    first.allocations.extend(
        [
            StockSaleAllocation(vesting_id=lot2.id, quantity=7),
            StockSaleAllocation(purchase_id=purchase.id, quantity=5),
        ]
    )
    db.session.delete(second)
    db.session.delete(third)
    db.session.commit()
    statement = prepare(context, overrides())["statements"][0]
    assert len(statement["lines"]) == 3
    assert [Decimal(line["fields"]["520"]) for line in statement["lines"]] == [100, 110, 120]
    assert sum(Decimal(line["fees_usd"]) for line in statement["lines"]) == Decimal("0.05")
    assert statement["computed"]["capital_result"] == "580"
    assert {line["grant_id"] for line in statement["lines"]} == {lot1.grant_id, lot2.grant_id, None}


def test_filing_year_and_family_filter_sales(app, context):
    selected, _ = sale(context)
    sale(context, sold=date(2023, 12, 31))
    sale(context, sold=date(2025, 1, 1))
    other = TaxReturn(family=Family(), year=2025)
    db.session.add(other)
    db.session.commit()
    sale(other, symbol="OTHER")
    view = prepare(context, overrides())
    assert [line["sale_id"] for statement in view["statements"] for line in statement["lines"]] == [
        selected.id
    ]


def test_rsu_residual_loss_and_incomplete_preparation_cannot_be_accepted(app, context):
    _, lot = sale(context, price="80", fees="1500")
    view = prepare(context, overrides())
    assert view["aggregate"]["3VH"] == "700"
    assert view["aggregate"]["1TZ"] == "0"
    lot.acquisition_fmv = 0
    db.session.commit()
    client = app.test_client()
    incomplete = preview(client, context).get_json()
    assert accept(client, context, incomplete).status_code == 422
    assert CapitalGainStatement.query.count() == 0


def test_first_use_downloads_and_caches_ecb_rates(app, monkeypatch):
    class Response:
        content = b'<Envelope><Cube><Cube time="2024-01-05"><Cube currency="USD" rate="1.25"/></Cube></Cube></Envelope>'

        def raise_for_status(self):
            pass

    calls = []
    monkeypatch.setattr(
        stock_fx.requests, "get", lambda *args, **kwargs: calls.append(args[0]) or Response()
    )
    assert FxResolver([date(2024, 1, 7)]).resolve(date(2024, 1, 7))[0] == Decimal("0.8")
    assert FxResolver([date(2024, 1, 8)]).resolve(date(2024, 1, 8))[0] == Decimal("0.8")
    assert calls == [stock_fx.ECB_HISTORY]
    assert UsdEurRate.query.count() == 1


def test_grant_entry_validates_approval_and_family_taxpayer(app, context):
    stock = Stock(family=context.family, name="Grant input", symbol="INPUT")
    db.session.add(stock)
    db.session.commit()
    client = app.test_client()
    body = {
        "grant_date": "2020-01-01",
        "vesting_start_date": "2020-01-01",
        "quantity": 10,
        "schedule_type": "quarterly",
        "customized": True,
        "vestings": [{"date": "2021-01-01", "quantity": 10}],
        "taxpayer_role": "taxpayer2",
    }
    url = f"/api/stocks/{stock.id}/grants"
    for approval in ("2015-08-08", "2016-12-31", "2018-01-01"):
        response = client.post(
            url, json={**body, "approval_date": approval}, headers={"Idempotency-Key": str(uuid4())}
        )
        assert response.status_code == 201
        assert response.get_json()["approval_date"] == approval
        assert response.get_json()["taxpayer_role"] == "taxpayer2"
    for change in (
        {"approval_date": "2015-08-07"},
        {"approval_date": "2018-01-01", "taxpayer_role": "child"},
    ):
        assert (
            client.post(
                url, json={**body, **change}, headers={"Idempotency-Key": str(uuid4())}
            ).status_code
            == 400
        )
    context.family.members.remove(context.family.taxpayer2)
    db.session.commit()
    assert (
        client.post(
            url,
            json={**body, "approval_date": "2018-01-01"},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 400
    )
