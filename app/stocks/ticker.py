from datetime import datetime, timedelta, date

import requests


class Ticker:
    url = "https://www.alphavantage.co/query"
    params = {"function": "GLOBAL_QUOTE", "apikey": "EO7TR7UYV9S82B0F"}
    # history_params = {"function": "TIME_SERIES_DAILY", "outputsize": "compact", "apikey": "EO7TR7UYV9S82B0F"}
    history_params = {"function": "TIME_SERIES_DAILY", "outputsize": "full", "apikey": "EO7TR7UYV9S82B0F"}
    cache = {}
    history_cache = {}

    def __init__(self, caching_time=timedelta(minutes=1), history_caching_time=timedelta(days=1)):
        self.caching_time = caching_time
        self.history_caching_time = history_caching_time

    def get_stock_value(self, symbol: str) -> str:
        if symbol in self.cache:
            price, timestamp = self.cache[symbol]
            current_time = datetime.now()
            if current_time - timestamp <= self.caching_time:
                return price
        params = self.params.copy()
        params["symbol"] = symbol
        response = requests.get(self.url, params=params)
        if response.status_code == 200:
            data = response.json()
            try:
                price = float(data['Global Quote']['05. price'])
                price_str = f"${round(price,2)}"
                timestamp = datetime.now()
                self.cache[symbol] = (price_str, timestamp)
                return price_str
            except:
                print("Error :", data)
        else:
            print("Error:", response.status_code)
            return "(error retrieve price)"

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
                for d,v in history_json.items():
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