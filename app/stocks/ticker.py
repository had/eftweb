from datetime import datetime, timedelta

import requests


class Ticker:
    url = "https://www.alphavantage.co/query"
    params = {"function": "GLOBAL_QUOTE", "apikey": "EO7TR7UYV9S82B0F"}
    cache = {}

    def __init__(self, caching_time=timedelta(minutes=1)):
        self.caching_time = caching_time

    def get_stock_value(self, symbol: str) -> str:
        print(self.cache)
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


ticker = Ticker()