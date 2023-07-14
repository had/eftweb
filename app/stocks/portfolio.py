from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, date

import requests
from easyfrenchtax import StockHelper, RsuTaxScheme

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

@dataclass
class PortfolioRsuVesting:
    vesting_date: date
    initial_amount: int
    currently_available: int

@dataclass
class PortfolioRsuPlan:
    plan_id: int
    name: str
    tax_scheme: RsuTaxScheme
    vestings: list[PortfolioRsuVesting]


class RSUPortfolio:
    def __init__(self, project_id):
        self.raw_plans = RSUPlan.query.filter_by(project_id=project_id).order_by(RSUPlan.symbol).all()

        self.stock_symbols = {s: ticker.get_stock_value(s) for s in [p.symbol for p in self.raw_plans]}

        self.plans = defaultdict(list)
        for p in self.raw_plans:
            vestings = RSUVesting.query.filter_by(rsu_plan_id=p.id).all()
            self.plans[p.symbol].append(PortfolioRsuPlan(
                plan_id=p.id,
                name=p.name,
                tax_scheme=StockHelper._determine_rsu_plans_type(p.approval_date),
                vestings=[PortfolioRsuVesting(
                    vesting_date=v.vesting_date,
                    initial_amount=v.count,
                    currently_available=v.count
                ) for v in vestings]))
        self.raw_sales = RSUSale.query.filter_by(project_id=project_id).all()


    def get_plans(self):
        return self.plans

    #
    # def get_stock_symbols(self) -> dict[str, str]:
    #     return {s: ticker.get_stock_value(s) for s in [p.stock_symbol for p in self.stock_helper.rsu_plans.values()]}
    #
    # def get_plans(self, symbol: str) -> list[PortfolioRsuPlan]:
    #     return list(filter(lambda p: p.stock_symbol == symbol, self.plans))
    #
    # def get_vestings(self, plan: PortfolioRsuPlan) -> list[PortfolioRsuVesting]:
    #     return [PortfolioRsuVesting(v.acq_date, v.count, v.available) for v in self.stock_helper.rsus[plan.plan.stock_symbol] if v.plan_name == plan.plan.name]
