"""Alpha Vantage prices shared by the legacy UI and stock quote API."""

import atexit
import json
import os
import tempfile
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from threading import Lock

import requests


class Ticker:
    url = "https://www.alphavantage.co/query"
    stockquery_params = {"function": "GLOBAL_QUOTE"}
    stockoverview_params = {"function": "OVERVIEW"}
    history_params = {"function": "TIME_SERIES_DAILY", "outputsize": "full"}
    query_stock_currency = False

    def __init__(
        self,
        caching_time=timedelta(hours=1),
        history_caching_time=timedelta(days=10),
        *,
        cache_filename=Path(__file__).resolve().parents[2] / "_eftweb_ticker_cache.json",
        now=None,
    ):
        self.caching_time = caching_time
        self.history_caching_time = history_caching_time
        self.retry_cooldown = timedelta(minutes=5)
        self.cache_filename = Path(cache_filename) if cache_filename is not None else None
        self._now = now or (lambda: datetime.now(UTC))
        self.stockvalue_cache = {}
        self.history_cache = {}
        self._failures = {}
        self._locks = {}
        self._locks_guard = Lock()
        self._cache_guard = Lock()
        if self.cache_filename is not None:
            try:
                with self.cache_filename.open(encoding="utf-8") as handle:
                    persisted = json.load(handle)
                if isinstance(persisted, dict):
                    for symbol, value in persisted.items():
                        entry = self._cache_entry(value)
                        if entry is not None:
                            self.stockvalue_cache[symbol.upper()] = entry
            except (OSError, ValueError):
                pass
            atexit.register(self._save_cache)

    def _lock(self, key):
        with self._locks_guard:
            return self._locks.setdefault(key, Lock())

    @staticmethod
    def _price(value):
        if isinstance(value, bool):
            raise ValueError("Invalid price")
        number = Decimal(str(value))
        if not number.is_finite() or number <= 0:
            raise ValueError("Invalid price")
        rounded = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if rounded <= 0:
            raise ValueError("Invalid price")
        return format(rounded, ".2f")

    @staticmethod
    def _timestamp(value):
        timestamp = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        return timestamp.astimezone(UTC)

    @staticmethod
    def _trading_date(value):
        try:
            parsed = date.fromisoformat(value)
            return value if parsed.isoformat() == value else None
        except (ValueError, TypeError):
            return None

    def _cache_entry(self, value):
        try:
            # Previous cache files stored [price, currency, naive local timestamp].
            if isinstance(value, (list, tuple)) and len(value) == 3:
                price, currency, timestamp = value
                trading_date = None
            elif isinstance(value, dict):
                price, currency, timestamp = value["price"], value["currency"], value["fetched_at"]
                trading_date = self._trading_date(value.get("quote_date"))
            else:
                return None
            if not isinstance(currency, str) or currency == "NOTICK":
                return None
            return {
                "price": self._price(price),
                "currency": currency,
                "fetched_at": self._timestamp(timestamp).isoformat(),
                "quote_date": trading_date,
            }
        except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError):
            return None

    def _save_cache(self):
        if self.cache_filename is None:
            return
        temporary = None
        try:
            with self._cache_guard:
                # Write only explicitly selected quote fields; never persist credentials or errors.
                data = {
                    symbol: entry
                    for symbol, value in self.stockvalue_cache.items()
                    if (entry := self._cache_entry(value)) is not None
                }
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self.cache_filename.parent,
                    prefix=".ticker-",
                    delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    json.dump(data, handle, allow_nan=False)
                os.replace(temporary, self.cache_filename)
        except OSError:
            pass
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _query_alphavantage(self, symbol: str, params: dict) -> dict:
        key = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
        if not key:
            return {}
        try:
            response = requests.get(
                self.url, params={**params, "symbol": symbol, "apikey": key}, timeout=(3, 7)
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}
        except (requests.RequestException, ValueError):
            # Request exception messages may contain the URL and API key. Do not log them.
            return {}

    def get_stock_quote(self, symbol: str) -> dict:
        symbol = symbol.strip().upper()
        with self._lock(("quote", symbol)):
            now = self._now()
            cached = self._cache_entry(self.stockvalue_cache.get(symbol))
            if cached and now - self._timestamp(cached["fetched_at"]) <= self.caching_time:
                return {"symbol": symbol, **cached, "stale": False, "error": None}
            last_failure = self._failures.get(symbol)
            if last_failure and now - last_failure[0] < self.retry_cooldown:
                return self._fallback(symbol, cached, last_failure[1])
            data = self._query_alphavantage(symbol, self.stockquery_params)
            try:
                quote = data["Global Quote"]
                if quote.get("01. symbol", symbol).strip().upper() != symbol:
                    raise ValueError("Wrong symbol")
                price = self._price(quote["05. price"])
                currency = "USD"
                if self.query_stock_currency:
                    currency = self._query_alphavantage(symbol, self.stockoverview_params)[
                        "Currency"
                    ]
                    if not isinstance(currency, str):
                        raise ValueError("Invalid currency")
                entry = {
                    "price": price,
                    "currency": currency,
                    "quote_date": self._trading_date(quote.get("07. latest trading day")),
                    "fetched_at": self._now().isoformat(),
                }
            except (KeyError, TypeError, ValueError, AttributeError, InvalidOperation):
                message = (
                    "Stock prices unavailable: ALPHAVANTAGE_API_KEY is not configured."
                    if not os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
                    else "Could not refresh the latest quote. The provider may be unavailable or rate-limited."
                )
                self._failures[symbol] = (self._now(), message)
                return self._fallback(symbol, cached, message)
            with self._cache_guard:
                self.stockvalue_cache[symbol] = entry
            self._failures.pop(symbol, None)
            self._save_cache()
            return {"symbol": symbol, **entry, "stale": False, "error": None}

    @staticmethod
    def _fallback(symbol, cached, message):
        return {
            "symbol": symbol,
            "price": None,
            "currency": "USD",
            "quote_date": None,
            "fetched_at": None,
            **(cached or {}),
            "stale": cached is not None,
            "error": message,
        }

    def get_stock_value(self, symbol: str) -> tuple[float, str]:
        quote = self.get_stock_quote(symbol)
        return (
            (float(quote["price"]), quote["currency"])
            if quote["price"] is not None
            else (float("nan"), "NOTICK")
        )

    def get_stock_closing_history(self, symbol: str) -> dict[date, float]:
        symbol = symbol.strip().upper()
        with self._lock(("history", symbol)):
            cached = self.history_cache.get(symbol)
            if cached and self._now() - self._timestamp(cached[1]) <= self.history_caching_time:
                return cached[0]
            data = self._query_alphavantage(symbol, self.history_params)
            try:
                history = {
                    date.fromisoformat(day): float(self._price(value["4. close"]))
                    for day, value in data["Time Series (Daily)"].items()
                }
            except (KeyError, TypeError, ValueError, AttributeError, InvalidOperation):
                return cached[0] if cached else {}
            self.history_cache[symbol] = (history, self._now())
            return history

    def get_historical_price_with_fallback(
        self, symbol: str, day: date, max_fallback_days: int = 5
    ) -> float:
        history = self.get_stock_closing_history(symbol)
        for _ in range(max_fallback_days):
            if day in history:
                return history[day]
            day -= timedelta(days=1)
        return float("inf")


ticker = Ticker()
