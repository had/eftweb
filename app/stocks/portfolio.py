from collections import defaultdict
from datetime import datetime, timedelta

import requests
from easyfrenchtax import StockHelper

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
        self.plans = defaultdict(list)
        for plan in rsu_plans:
            plan_tax_scheme = StockHelper._determine_rsu_plans_type(plan.grant_date)
            vestings =  RSUVesting.query.filter_by(rsu_plan_id=plan.id).all()
            self.plans[plan.symbol].append((plan, plan_tax_scheme, vestings))
        self.stock_symbols = {s: ticker.get_stock_value(s) for s in [p.symbol for p in rsu_plans]}
        self.sales = RSUSale.query.filter_by(project_id=project_id).all()

    # def get_rsu_plans(self):
    #     # self.helper = build_stock_helper(
    #     #     year=2023,
    #     #     direct_stocks=[],
    #     #     dstock_sales_that_year=[],
    #     #     rsu_plans=self.unsorted_rsu_plans,
    #     #     rsu_vestings=self.unsorted_rsu_vestings,
    #     #     rsu_sales_that_year=self.sales
    #     # )
    #     res = {}
    #     for symbol, plans in self.plans:
    #         plist = []
    #         for p in plans:
    #             plan_tax_scheme = StockHelper._determine_rsu_plans_type(p.grant_date)
    #             plist.append(plan_tax_scheme, p)