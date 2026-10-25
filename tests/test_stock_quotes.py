import json
import math
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest
import requests

from app import create_app, db, load_environment
from config import TestingConfig


@pytest.fixture()
def clock():
    return [datetime(2026, 10, 25, 12, tzinfo=UTC)]


@pytest.fixture()
def service(monkeypatch, clock):
    create_app("testing")
    from app.stocks.ticker import Ticker

    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test-secret-key")

    def no_network(*args, **kwargs):
        raise AssertionError("Unexpected unmocked provider request")

    monkeypatch.setattr(requests, "get", no_network)
    return Ticker(cache_filename=None, now=lambda: clock[0])


def response(data, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(data).encode()
    return result


def quote_data(price="123.455", symbol="AAPL"):
    return {
        "Global Quote": {
            "01. symbol": symbol,
            "05. price": price,
            "07. latest trading day": "2026-10-23",
        }
    }


def test_dotenv_environment_precedence_and_ignored_credentials(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("ALPHAVANTAGE_API_KEY=file-key\n")
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    load_environment(env)
    import os

    assert os.environ["ALPHAVANTAGE_API_KEY"] == "file-key"
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "deployment-key")
    load_environment(env)
    assert os.environ["ALPHAVANTAGE_API_KEY"] == "deployment-key"
    assert subprocess.run(["git", "check-ignore", "-q", ".env"], check=False).returncode == 0
    assert not subprocess.check_output(["git", "ls-files", ".env"]).strip()


def test_factory_loads_root_environment_before_registering_routes(monkeypatch):
    called = []
    monkeypatch.setattr("app.load_environment", lambda: called.append(True))
    create_app("testing")
    assert called == [True]


def test_quote_metadata_rounding_and_cache_hit(service, monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(kwargs)
        return response(quote_data())

    monkeypatch.setattr(requests, "get", get)
    quote = service.get_stock_quote(" aapl ")
    assert quote == {
        "symbol": "AAPL",
        "price": "123.46",
        "currency": "USD",
        "quote_date": "2026-10-23",
        "fetched_at": "2026-10-25T12:00:00+00:00",
        "stale": False,
        "error": None,
    }
    assert service.get_stock_value("AAPL") == (123.46, "USD")
    assert service.get_stock_quote("AAPL") == quote
    assert len(calls) == 1
    assert calls[0]["params"]["apikey"] == "test-secret-key"
    assert calls[0]["timeout"] == (3, 7)
    assert "symbol" not in service.stockquery_params
    assert "apikey" not in service.stockquery_params
    assert "test-secret-key" not in json.dumps(quote)


def test_cache_expiry_stale_fallback_and_retry_cooldown(service, clock, monkeypatch):
    calls = []

    def get(*args, **kwargs):
        calls.append(True)
        return response(
            quote_data()
            if len(calls) == 1 or len(calls) == 3
            else {"Information": "quota exceeded"}
        )

    monkeypatch.setattr(requests, "get", get)
    original = service.get_stock_quote("AAPL")
    clock[0] += timedelta(hours=2)
    stale = service.get_stock_quote("AAPL")
    assert stale["price"] == original["price"]
    assert stale["fetched_at"] == original["fetched_at"]
    assert stale["stale"] is True
    assert stale["error"]
    service.get_stock_quote("AAPL")
    assert len(calls) == 2
    clock[0] += timedelta(minutes=5)
    fresh = service.get_stock_quote("AAPL")
    assert len(calls) == 3
    assert fresh["stale"] is False
    assert fresh["fetched_at"] != original["fetched_at"]


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"Global Quote": {}},
        {"Global Quote": []},
        {"Note": "rate limit"},
        quote_data("NaN"),
        quote_data("Infinity"),
        quote_data("-1"),
        quote_data("0"),
        quote_data("bad"),
        quote_data(True),
        quote_data("123.45", "MSFT"),
    ],
)
def test_invalid_provider_data_returns_safe_unavailable_quote(service, monkeypatch, data):
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response(data))
    result = service.get_stock_quote("AAPL")
    assert result["price"] is None
    assert result["fetched_at"] is None
    assert result["error"]
    json.dumps(result, allow_nan=False)
    value, currency = service.get_stock_value("AAPL")
    assert math.isnan(value)
    assert currency == "NOTICK"


@pytest.mark.parametrize("failure", ["timeout", "http", "json"])
def test_request_errors_do_not_leak_keys(service, monkeypatch, capsys, caplog, failure):
    def get(*args, **kwargs):
        if failure == "timeout":
            raise requests.Timeout("https://provider.example?apikey=test-secret-key")
        if failure == "http":
            return response({}, 503)
        result = response({})
        result._content = b"not json"
        return result

    monkeypatch.setattr(requests, "get", get)
    result = service.get_stock_quote("AAPL")
    assert result["price"] is None
    assert "test-secret-key" not in json.dumps(result) + capsys.readouterr().out + caplog.text


def test_missing_key_skips_requests_and_can_serve_legacy_cache(service, clock, monkeypatch):
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY")
    result = service.get_stock_quote("AAPL")
    assert result["price"] is None
    assert "not configured" in result["error"]
    service.stockvalue_cache["MSFT"] = [100.25, "USD", (clock[0] - timedelta(hours=2)).isoformat()]
    result = service.get_stock_quote("MSFT")
    assert result["price"] == "100.25"
    assert result["quote_date"] is None
    assert result["stale"] is True
    assert service.get_stock_closing_history("MSFT") == {}


def test_existing_cache_file_loads_and_new_format_round_trips(
    service, clock, tmp_path, monkeypatch
):
    from app.stocks.ticker import Ticker

    path = tmp_path / "cache.json"
    path.write_text(
        json.dumps(
            {
                "AAPL": [123.45, "USD", clock[0].replace(tzinfo=None).isoformat()],
                "BAD": ["nan", "USD", clock[0].isoformat()],
            }
        )
    )
    loaded = Ticker(cache_filename=path, now=lambda: clock[0])
    assert "BAD" not in loaded.stockvalue_cache
    assert loaded.stockvalue_cache["AAPL"]["price"] == "123.45"
    assert loaded.stockvalue_cache["AAPL"]["quote_date"] is None
    loaded._save_cache()
    assert "test-secret-key" not in path.read_text()
    restarted = Ticker(cache_filename=path, now=lambda: clock[0])
    assert restarted.stockvalue_cache == loaded.stockvalue_cache
    # Disable exit writes after pytest removes its temporary directory.
    loaded.cache_filename = restarted.cache_filename = None


def test_simultaneous_quote_requests_are_coalesced(service, monkeypatch):
    entered, release = Event(), Event()
    calls = []

    def get(*args, **kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(2)
        return response(quote_data())

    monkeypatch.setattr(requests, "get", get)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.get_stock_quote, "AAPL")
        assert entered.wait(2)
        second = pool.submit(service.get_stock_quote, "AAPL")
        release.set()
        assert first.result() == second.result()
    assert len(calls) == 1


def test_quote_overview_and_history_share_environment_configuration(service, monkeypatch):
    calls = []

    def get(url, params, timeout):
        calls.append(params)
        if params["function"] == "OVERVIEW":
            return response({"Currency": "EUR"})
        if params["function"] == "TIME_SERIES_DAILY":
            return response({"Time Series (Daily)": {"2026-10-23": {"4. close": "99.10"}}})
        return response(quote_data())

    monkeypatch.setattr(requests, "get", get)
    service.query_stock_currency = True
    assert service.get_stock_value("AAPL") == (123.46, "EUR")
    assert list(service.get_stock_closing_history("AAPL").values()) == [99.1]
    assert {call["function"] for call in calls} == {"GLOBAL_QUOTE", "OVERVIEW", "TIME_SERIES_DAILY"}
    assert all(call["apikey"] == "test-secret-key" for call in calls)
    assert all(
        "apikey" not in params
        for params in (
            service.stockquery_params,
            service.stockoverview_params,
            service.history_params,
        )
    )


def test_quote_api_handles_active_archived_missing_and_non_usd_stocks(service, monkeypatch):
    from app.api import stock_quotes
    from app.family.models import Family
    from app.stocks.models import Stock

    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    app = create_app("testing")
    monkeypatch.setattr(stock_quotes, "ticker", service)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response(quote_data()))
    with app.app_context():
        db.create_all()
        stock = Stock(family=Family(), name="Apple", symbol="AAPL")
        db.session.add(stock)
        db.session.commit()
        client = app.test_client()
        endpoint = f"/api/stocks/{stock.id}/quote"
        assert client.get(endpoint).get_json()["price"] == "123.46"
        stock.is_archived = True
        db.session.commit()
        assert client.get(endpoint).status_code == 200
        assert client.get("/api/stocks/9999/quote").status_code == 404
        service.stockvalue_cache["AAPL"]["currency"] = "EUR"
        non_usd = client.get(endpoint).get_json()
        assert non_usd["currency"] == "USD"
        assert non_usd["price"] is None
        stock.family.is_archived = True
        db.session.commit()
        assert client.get(endpoint).status_code == 410
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
