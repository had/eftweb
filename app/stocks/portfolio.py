import itertools
from datetime import datetime, timedelta

import requests

from app.stocks.models import RSUPlan, RSUVesting, RSUSale

class Ticker:
    url = "https://www.alphavantage.co/query"
    params = {"function": "GLOBAL_QUOTE","apikey": "EO7TR7UYV9S82B0F"}
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
                price = f"${data['Global Quote']['05. price']}"
                timestamp = datetime.now()
                self.cache[symbol] = (price, timestamp)
                return price
            except:
                print("Error :", data)
        else:
            print("Error:", response.status_code)
            return "(error retrieve price)"

ticker = Ticker()

class RSUPortfolio:
    def __init__(self, project_id):
        rsu_plans = RSUPlan.query.filter_by(project_id=project_id).order_by(RSUPlan.symbol).all()
        self.plans = itertools.groupby(rsu_plans, lambda p: p.symbol)
        self.stock_symbols = {s: ticker.get_stock_value(s) for s in ([p.symbol for p in rsu_plans])}
        rsu_plans_id = [p.id for p in rsu_plans]
        rsu_vestings = RSUVesting.query.filter(RSUVesting.rsu_plan_id.in_(rsu_plans_id)).all()
        self.vestings = {plan_id: list(v) for plan_id, v in itertools.groupby(rsu_vestings, key=lambda x: x.rsu_plan_id)}
        self.sales = RSUSale.query.filter_by(project_id=project_id).all()
