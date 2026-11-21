"""Current-ledger stock taxation and stable, serializable declaration helpers."""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from dateutil.relativedelta import relativedelta

from app import db
from app.family.models import CapitalGainStatement
from app.stocks.import_parsers import fingerprint
from app.stocks.models import GrantVesting, Stock, StockPurchase, StockSale
from app.stocks.tax_inputs import split_cents

from .stock_fx import FxResolver

FIELDS = ("capital_result", "1TZ", "1UZ", "1WZ", "1TT", "1UT")


def whole(value):
    return str(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def empty_values():
    return dict.fromkeys(FIELDS, "0")


def reported_values(data, base=None):
    if not isinstance(data, dict) or set(data) - set(FIELDS):
        raise ValueError("Provide supported statement contributions only")
    result = dict(base or empty_values())
    for field, raw in data.items():
        try:
            if isinstance(raw, bool):
                raise ValueError()
            value = Decimal(str(raw))
            if (
                not value.is_finite()
                or value != value.to_integral_value()
                or abs(value) >= Decimal("1e24")
            ):
                raise ValueError()
            if field != "capital_result" and value < 0:
                raise ValueError()
        except (ValueError, ArithmeticError):
            raise ValueError(
                f"{field} must be a {'signed ' if field == 'capital_result' else 'non-negative '}whole EUR amount"
            ) from None
        result[field] = whole(value)
    return result


def aggregate(statements):
    values = defaultdict(Decimal)
    for statement in statements:
        data = statement.reported if hasattr(statement, "reported") else statement["reported"]
        for field in FIELDS:
            values[field] += Decimal(data.get(field, "0"))
    capital = values.pop("capital_result", Decimal(0))
    return {
        **{field: whole(values[field]) for field in FIELDS if field != "capital_result"},
        "3VG": whole(max(capital, 0)),
        "3VH": whole(max(-capital, 0)),
    }


def regime(approval):
    if approval is None:
        raise ValueError("Missing RSU shareholder approval date")
    if approval < date(2015, 8, 8):
        raise ValueError("Unsupported RSU regime: approval before 2015-08-08")
    if approval < date(2016, 12, 31):
        return "Macron I"
    if approval < date(2018, 1, 1):
        return "Macron II"
    return "Macron III"


def ledger(tax_return):
    start, end = date(tax_return.year - 1, 1, 1), date(tax_return.year, 1, 1)
    sales = (
        StockSale.query.join(Stock)
        .filter(
            Stock.family_id == tax_return.family_id,
            StockSale.transaction_date >= start,
            StockSale.transaction_date < end,
        )
        .order_by(StockSale.transaction_date, Stock.symbol, StockSale.id)
        .all()
    )
    entries, dates, facts = [], set(), []
    for sale in sales:
        dates.add(sale.transaction_date)
        source = {"stock": sale.stock.to_dict(), "sale": sale.to_dict(), "lots": []}
        weights = [Decimal(a.quantity) * sale.proceeds_per_share for a in sale.allocations]
        fees = split_cents(sale.fees or 0, weights)
        for allocation, fee in zip(sale.allocations, fees, strict=True):
            rsu = allocation.vesting_id is not None
            lot = db.session.get(
                GrantVesting if rsu else StockPurchase,
                allocation.vesting_id if rsu else allocation.purchase_id,
            )
            if lot is None:
                raise ValueError("A recorded sale references a missing acquisition")
            acquired = lot.date if rsu else lot.purchase_date
            dates.add(acquired)
            grant = lot.grant if rsu else None
            source["lots"].append(
                {"lot": lot.to_dict(), "grant": grant.to_dict() if grant else None}
            )
            entries.append((sale, allocation, lot, acquired, grant, fee))
        facts.append(source)
    return entries, dates, facts


def prepare(tax_return, overrides=None, refresh=True):
    with localcontext() as ctx:
        ctx.prec = 50
        return _prepare(tax_return, overrides, refresh)


def _prepare(tax_return, overrides, refresh):
    entries, dates, facts = ledger(tax_return)
    resolver = FxResolver(dates, overrides, refresh=refresh)
    existing = (
        CapitalGainStatement.query.filter_by(tax_return_id=tax_return.id)
        .order_by(CapitalGainStatement.id)
        .all()
    )
    saved = [statement.to_dict(details=True) for statement in existing]
    errors = [
        f"{f['stock']['symbol']} · sale {f['sale']['id']}: missing or inconsistent acquisition allocations"
        for f in facts
        if not f["sale"]["allocations"]
        or sum(a["quantity"] for a in f["sale"]["allocations"]) != f["sale"]["quantity"]
    ]
    by_stock = {}
    remaining = {"taxpayer1": Decimal(300000), "taxpayer2": Decimal(300000)}
    for sale, allocation, lot, acquired, grant, fee in sorted(
        entries,
        key=lambda row: (row[0].transaction_date, row[0].stock.symbol, row[0].id, row[1].id),
    ):
        try:
            if not lot.acquisition_fmv or lot.acquisition_fmv <= 0:
                raise ValueError(
                    f"Missing acquisition FMV for {'vesting' if grant else 'purchase'} {lot.id}"
                )
            scheme = regime(grant.approval_date) if grant else None
            role = grant.taxpayer_role if grant else None
            if grant and (role not in remaining or not getattr(tax_return.family, role, None)):
                raise ValueError(f"Missing or invalid taxpayer assignment for grant {grant.title}")
            acquisition_rate, acquisition_fx = resolver.resolve(acquired)
            selling_rate, selling_fx = resolver.resolve(sale.transaction_date)
        except ValueError as error:
            errors.append(f"{sale.stock.symbol} · sale {sale.id}: {error}")
            continue
        quantity = Decimal(allocation.quantity)
        unit_basis = lot.acquisition_fmv * acquisition_rate
        unit_sale = sale.proceeds_per_share * selling_rate
        gross, basis, fee_eur = unit_sale * quantity, unit_basis * quantity, fee * selling_rate
        net = gross - fee_eur
        # The disposal decline reduces the matching RSU acquisition gain, once only.
        absorbed = min(basis, max(basis - net, Decimal(0))) if grant else Decimal(0)
        acquisition_gain = basis - absorbed if grant else Decimal(0)
        capital = (
            Decimal(whole(net - basis + absorbed))
            if absorbed
            else Decimal(whole(net)) - Decimal(whole(basis))
        )
        low, excess, rebate, rebate50 = Decimal(0), Decimal(0), Decimal(0), Decimal(0)
        if grant:
            low = (
                acquisition_gain if scheme == "Macron I" else min(acquisition_gain, remaining[role])
            )
            excess = acquisition_gain - low
            if scheme != "Macron I":
                remaining[role] -= low
            if scheme == "Macron III":
                rebate50 = low * Decimal("0.5")
            elif acquired <= sale.transaction_date - relativedelta(years=8):
                rebate = low * Decimal("0.65")
            elif acquired <= sale.transaction_date - relativedelta(years=2):
                rebate = low * Decimal("0.5")
        contributions = {
            "capital_result": capital,
            "1TZ": low - rebate - rebate50,
            "1UZ": rebate,
            "1WZ": rebate50,
            "1TT": excess if role == "taxpayer1" else Decimal(0),
            "1UT": excess if role == "taxpayer2" else Decimal(0),
        }
        line = {
            "stock_id": sale.stock_id,
            "sale_id": sale.id,
            "allocation_id": allocation.id,
            "grant_id": grant.id if grant else None,
            "acquisition_id": lot.id,
            "acquisition_type": "RSU" if grant else "ESPP",
            "grant_title": grant.title if grant else None,
            "approval_date": grant.approval_date.isoformat() if grant else None,
            "taxpayer_role": role,
            "regime": scheme,
            "acquisition_date": acquired.isoformat(),
            "acquisition_fmv_usd": str(lot.acquisition_fmv),
            "selling_price_usd": str(sale.proceeds_per_share),
            "fees_usd": format(fee, ".2f"),
            "acquisition_fx": acquisition_fx,
            "selling_fx": selling_fx,
            "acquisition_value_usd": format(lot.acquisition_fmv * quantity, "f"),
            "proceeds_usd": format(sale.proceeds_per_share * quantity, "f"),
            "acquisition_value_eur": format(basis, "f"),
            "proceeds_eur": format(gross, "f"),
            "fees_eur": format(fee_eur, "f"),
            "acquisition_gain": format(acquisition_gain, "f"),
            "absorbed_loss": format(absorbed, "f"),
            "threshold_eligible": format(low, "f"),
            "threshold_excess": format(excess, "f"),
            "contributions": {key: whole(value) for key, value in contributions.items()},
            "fields": {
                "511": sale.stock.symbol + (" RSU" if grant else " ESPP"),
                "512": sale.transaction_date.isoformat(),
                "514": format(unit_sale, "f"),
                "515": str(allocation.quantity),
                "516": whole(gross),
                "517": whole(fee_eur),
                "518": whole(net),
                "520": format(unit_basis, "f"),
                "521": whole(basis),
                "522": "0",
                "523": whole(basis),
                "524": whole(Decimal(whole(net)) - Decimal(whole(basis))),
            },
        }
        statement = by_stock.setdefault(
            sale.stock_id,
            {
                "stock_id": sale.stock_id,
                "title": f"{sale.stock.symbol} · {tax_return.year - 1} stock sales",
                "source_key": f"stock:{sale.stock_id}",
                "lines": [],
                "metadata": {
                    "income_year": tax_return.year - 1,
                    "symbol": sale.stock.symbol,
                    "stock_name": sale.stock.name,
                    "calculation_version": 1,
                },
                "_amounts": defaultdict(Decimal),
            },
        )
        statement["lines"].append(line)
        # Match capital totals to rounded report lines. Aggregate acquisition boxes before rounding.
        for field, value in contributions.items():
            statement["_amounts"][field] += value
    statements = list(by_stock.values())
    for statement in statements:
        statement["computed"] = {field: whole(statement["_amounts"][field]) for field in FIELDS}
        statement["reported"] = dict(statement["computed"])
        del statement["_amounts"]
    threshold = {
        role: {"used": format(Decimal(300000) - value, "f"), "remaining": format(value, "f")}
        for role, value in remaining.items()
    }
    revision = fingerprint(
        {
            "return": tax_return.to_dict(),
            "taxpayers": [bool(tax_return.family.taxpayer1), bool(tax_return.family.taxpayer2)],
            "ledger": facts,
            "saved": saved,
            "computed": statements,
            "threshold": threshold,
            "overrides": overrides or {},
        }
    )
    return {
        "income_year": tax_return.year - 1,
        "filing_year": tax_return.year,
        "source_revision": revision,
        "statements": statements,
        "errors": errors,
        "can_accept": not errors,
        "threshold": threshold,
        "replacements": [s for s in saved if s["source_key"] is not None],
        "aggregate": aggregate(statements + [s for s in saved if s["source_key"] is None]),
    }
