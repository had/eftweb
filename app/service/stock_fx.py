"""ECB historical reference rates. No extrapolation outside downloaded coverage."""

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import requests
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.family.models import FxCoverage, UsdEurRate

ECB_HISTORY = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"


def parse_ecb(content):
    if len(content) > 20 * 1024 * 1024 or b"<!DOCTYPE" in content.upper():
        raise ValueError("Invalid ECB rate document")
    root = ElementTree.fromstring(content)
    rates = {}
    for element in root.iter():
        if "time" not in element.attrib:
            continue
        day = datetime.strptime(element.attrib["time"], "%Y-%m-%d").date()
        for quote in element:
            if quote.attrib.get("currency") == "USD":
                rate = Decimal(quote.attrib["rate"])
                if not rate.is_finite() or rate <= 0 or rate >= 1000:
                    raise ValueError("Invalid ECB USD rate")
                rates[day] = rate
    if not rates:
        raise ValueError("ECB document has no USD rates")
    return rates


def refresh_rates():
    response = requests.get(ECB_HISTORY, timeout=(5, 15))
    response.raise_for_status()
    rates = parse_ecb(response.content)
    today = datetime.now(ZoneInfo("Europe/Paris")).date()
    if max(rates) > today:
        raise ValueError("ECB document contains future rates")
    # A downloaded complete series covers publication holidays up to retrieval day.
    for day, rate in rates.items():
        row = db.session.get(UsdEurRate, day)
        if row is None:
            db.session.add(UsdEurRate(date=day, usd_per_eur=rate, source="ECB"))
        else:
            row.usd_per_eur = rate
    coverage = db.session.get(FxCoverage, 1)
    if coverage is None:
        coverage = FxCoverage(id=1)
        db.session.add(coverage)
    coverage.first_date, coverage.last_date = min(rates), today
    db.session.commit()


class FxResolver:
    def __init__(self, dates, overrides=None, refresh=True):
        self.overrides = {}
        if overrides is None:
            overrides = {}
        if not isinstance(overrides, dict):
            raise ValueError("FX overrides must map event dates to EUR per USD rates")
        for day, value in overrides.items():
            try:
                parsed = datetime.strptime(day, "%Y-%m-%d").date()
                if parsed.isoformat() != day or isinstance(value, bool):
                    raise ValueError()
                rate = Decimal(str(value))
                if not rate.is_finite() or not 0 < rate < 1000 or rate.as_tuple().exponent < -12:
                    raise ValueError()
            except (TypeError, ValueError, InvalidOperation):
                raise ValueError(f"Invalid EUR per USD override for {day}") from None
            self.overrides[day] = rate
        self.coverage = db.session.get(FxCoverage, 1)
        automatic = [day for day in dates if day.isoformat() not in self.overrides]
        missing = any(not self._covered(day) or self._row(day) is None for day in automatic)
        if missing and refresh:
            try:
                refresh_rates()
            except (
                requests.RequestException,
                ValueError,
                ElementTree.ParseError,
                SQLAlchemyError,
                InvalidOperation,
            ):
                db.session.rollback()
            self.coverage = db.session.get(FxCoverage, 1)

    def _covered(self, day):
        return (
            self.coverage is not None and self.coverage.first_date <= day <= self.coverage.last_date
        )

    @staticmethod
    def _row(day):
        return (
            UsdEurRate.query.filter(
                UsdEurRate.date <= day, UsdEurRate.date >= day - timedelta(days=7)
            )
            .order_by(UsdEurRate.date.desc())
            .first()
        )

    def resolve(self, day):
        text = day.isoformat()
        if text in self.overrides:
            rate = self.overrides[text]
            return rate, {
                "event_date": text,
                "rate_date": text,
                "source": "Manual",
                "direction": "EUR per USD",
                "rate": str(rate),
            }
        row = self._row(day) if self._covered(day) else None
        if row is None:
            raise ValueError(f"USD/EUR rate unavailable for {text}; enter an EUR per USD rate")
        return Decimal(1) / row.usd_per_eur, {
            "event_date": text,
            "rate_date": row.date.isoformat(),
            "source": row.source,
            "direction": "USD per EUR",
            "rate": str(row.usd_per_eur),
        }
