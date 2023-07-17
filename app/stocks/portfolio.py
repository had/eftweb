from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import DefaultDict

from currency_converter import CurrencyConverter

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
    acquisition_price_eur: float

@dataclass
class PortfolioRsuPlan:
    plan_id: int
    name: str
    symbol: str
    tax_scheme: RsuTaxScheme
    vestings: list[PortfolioRsuVesting]

@dataclass
class RSUPortfolioSalesFragment:
    symbol: str
    nb_stocks_sold: int
    acq_date: date
    unit_acquisition_price: float
    sell_date: date
    sell_price_eur: float
    tax_scheme: RsuTaxScheme

class RSUPortfolio:
    plans: DefaultDict[str, list[PortfolioRsuPlan]]
    sales_fragment: list[RSUPortfolioSalesFragment]

    def __init__(self, project_id):
        # currency converter (USD/EUR in particular)
        self.cc = CurrencyConverter(fallback_on_wrong_date=True, fallback_on_missing_rate=True)
        self.raw_plans = RSUPlan.query.filter_by(project_id=project_id).order_by(RSUPlan.symbol).all()
        self.stock_symbols = {s: ticker.get_stock_value(s) for s in [p.symbol for p in self.raw_plans]}
        self.plans = defaultdict(list)
        for p in self.raw_plans:
            vestings = RSUVesting.query.filter_by(rsu_plan_id=p.id).all()
            self.plans[p.symbol].append(PortfolioRsuPlan(
                plan_id=p.id,
                name=p.name,
                symbol=p.symbol,
                tax_scheme=StockHelper._determine_rsu_plans_type(p.approval_date),
                vestings=[PortfolioRsuVesting(
                    vesting_date=v.vesting_date,
                    initial_amount=v.count,
                    currently_available=v.count,
                    acquisition_price_eur=self.cc.convert(v.acquisition_price, p.stock_currency, "EUR")
                ) for v in vestings]))
        self.raw_sales = RSUSale.query.filter_by(project_id=project_id).all()
        self.sales_fragment = []
        for s in self.raw_sales:
            self.process_sale(s)


    def get_plans(self):
        return self.plans

    def process_sale(self, sale_event: RSUSale):
        sell_date = sale_event.sell_date
        sell_price_eur = round(self.cc.convert(sale_event.sell_price, sale_event.sell_currency, "EUR", date=sell_date), 2)
        to_sell = sale_event.quantity

        # Acquisitions are sorted by date, this is the rule set by the tax office (FIFO, or PEPS="premier entré premier
        # sorti"); we only keep stocks acquired *before* the sell date, in case we input a sell event in the middle of
        # acquisitions.
        rsu_before_sell_date = sorted(
            [(p,r) for p in self.plans[sale_event.symbol] for r in p.vestings if r.vesting_date < sell_date],
            key=lambda pr: pr[1].vesting_date
        )

        for i, (plan, vesting) in enumerate(rsu_before_sell_date):
            if vesting.currently_available == 0:
                continue
            sell_from_acq = min(to_sell, vesting.currently_available)
            tax_scheme = plan.tax_scheme
            self.sales_fragment.append(RSUPortfolioSalesFragment(
                symbol=plan.symbol,
                nb_stocks_sold=sell_from_acq,
                acq_date=vesting.vesting_date,
                unit_acquisition_price=vesting.acquisition_price_eur,
                sell_date=sell_date,
                sell_price_eur=sell_price_eur,
                tax_scheme=tax_scheme
            ))
            vesting.currently_available = vesting.currently_available - sell_from_acq
            to_sell -= sell_from_acq
            if to_sell == 0:
                break
        if to_sell > 0:
            print(f"WARNING: You are trying to sell more stocks than you have")
        return

    #
    # def get_stock_symbols(self) -> dict[str, str]:
    #     return {s: ticker.get_stock_value(s) for s in [p.stock_symbol for p in self.stock_helper.rsu_plans.values()]}
    #
    # def get_plans(self, symbol: str) -> list[PortfolioRsuPlan]:
    #     return list(filter(lambda p: p.stock_symbol == symbol, self.plans))
    #
    # def get_vestings(self, plan: PortfolioRsuPlan) -> list[PortfolioRsuVesting]:
    #     return [PortfolioRsuVesting(v.acq_date, v.count, v.available) for v in self.stock_helper.rsus[plan.plan.stock_symbol] if v.plan_name == plan.plan.name]
