from datetime import datetime, timedelta, date
from typing import Tuple

import requests
import locale


class Ticker:
    url = "https://www.alphavantage.co/query"
    stockquery_params = {"function": "GLOBAL_QUOTE", "apikey": "EO7TR7UYV9S82B0F"}
    stockoverview_params = {"function": "OVERVIEW", "apikey": "EO7TR7UYV9S82B0F"}
    stockvalue_cache = {}
    history_params = {"function": "TIME_SERIES_DAILY", "outputsize": "full", "apikey": "EO7TR7UYV9S82B0F"}
    history_cache = {}

    # if True, we use the OVERVIEW function to get the currency of a given stock
    # this is usually set to False otherwise we quickly hit the limits of the "free" plan (10 calls per minute)
    query_stock_currency = False

    def __init__(self, caching_time=timedelta(minutes=1), history_caching_time=timedelta(days=1)):
        self.caching_time = caching_time
        self.history_caching_time = history_caching_time

    def _query_alphavantage(self, symbol: str, params: dict) -> dict:
        params["symbol"] = symbol
        response = requests.get(self.url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print("Error:", response.status_code)
            return {}

    def get_stock_value(self, symbol: str) -> Tuple[float, str]:
        if symbol in self.stockvalue_cache:
            price, currency, timestamp = self.stockvalue_cache[symbol]
            current_time = datetime.now()
            if current_time - timestamp <= self.caching_time:
                return price, currency
        price_data = self._query_alphavantage(symbol, self.stockquery_params)
        price = round(float(price_data['Global Quote']['05. price']), 2)
        if self.query_stock_currency:
            currency_data = self._query_alphavantage(symbol, self.stockoverview_params)
            currency = currency_data["Currency"]
        else:
            currency = "USD"
        self.stockvalue_cache[symbol] = (price, currency, datetime.now())
        return price, currency

    def get_stock_closing_history(self, symbol: str) -> dict[date, float]:
        print("Ticker.get_stock_closing_history.cache = ", self.history_cache)
        if symbol in self.history_cache:
            history, timestamp = self.history_cache[symbol]
            current_time = datetime.now()
            if current_time - timestamp <= self.history_caching_time:
                return history
        params = self.history_params.copy()
        params["symbol"] = symbol
        response = requests.get(self.url, params=params)
        if response.status_code == 200:
            data = response.json()
            try:
                history_json = data['Time Series (Daily)']
                history = {}
                for d, v in history_json.items():
                    history[datetime.strptime(d, "%Y-%m-%d").date()] = round(float(v["4. close"]), 2)
                timestamp = datetime.now()
                self.history_cache[symbol] = (history, timestamp)
                return history
            except:
                print("Error :", data)
        else:
            print("Error:", response.status_code)
            return {}


ticker = Ticker()


class CurrencySymbols:
    locales = ('en_GB.UTF-8', 'zh_HK.UTF-8', 'en_IE.UTF-8', 'en_US.UTF-8', 'ja_JP.UTF-8')
    currency_symbols: dict[str, str]

    def __init__(self):
        self.currency_symbols = {}
        for l in self.locales:
            locale.setlocale(locale.LC_ALL, l)
            conv = locale.localeconv()
            self.currency_symbols[conv['int_curr_symbol']] = conv['currency_symbol']
        locale.setlocale(locale.LC_ALL, "")

    def get(self, currency_code: str) -> str:
        return self.currency_symbols[currency_code]


currency_symbols = CurrencySymbols()
