from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import DefaultDict, Optional

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
    nb_stocks_sold: int
    acq_date: date
    unit_acquisition_price: float
    tax_scheme: RsuTaxScheme

@dataclass
class RSUPortfolioSale:
    sale_id: int
    symbol: str
    sell_date: date
    quantity: int
    sell_price: float
    sell_currency: str
    fragments: list[RSUPortfolioSalesFragment]
    sell_price_eur: float
    taxes: Optional[int] = None


class RSUPortfolio:
    plans: DefaultDict[str, list[PortfolioRsuPlan]]
    sales: list[RSUPortfolioSale]

    def __init__(self, project_id):
        # currency converter (USD/EUR in particular)
        self.cc = CurrencyConverter(fallback_on_wrong_date=True, fallback_on_missing_rate=True)
        raw_plans = RSUPlan.query.filter_by(project_id=project_id).order_by(RSUPlan.symbol).all()
        self.stock_symbols = {s: ticker.get_stock_value(s) for s in [p.symbol for p in raw_plans]}
        self.plans = defaultdict(list)
        for p in raw_plans:
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
        raw_sales = RSUSale.query.filter_by(project_id=project_id).all()
        # self.sales_fragment = []
        self.sales = []
        for s in raw_sales:
            portfolio_sale = self.process_sale(s)
            self.process_taxes(portfolio_sale)

    def get_plans(self):
        return self.plans

    def process_sale(self, sale_event: RSUSale):
        sell_date = sale_event.sell_date
        sell_price_eur = round(self.cc.convert(sale_event.sell_price, sale_event.sell_currency.upper(), "EUR", date=sell_date), 2)
        to_sell = sale_event.quantity

        # Acquisitions are sorted by date, this is the rule set by the tax office (FIFO, or PEPS="premier entré premier
        # sorti"); we only keep stocks acquired *before* the sell date, in case we input a sell event in the middle of
        # acquisitions.
        rsu_before_sell_date = sorted(
            [(p,r) for p in self.plans[sale_event.symbol] for r in p.vestings if r.vesting_date < sell_date],
            key=lambda pr: pr[1].vesting_date
        )

        sales_fragment = []
        for i, (plan, vesting) in enumerate(rsu_before_sell_date):
            if vesting.currently_available == 0:
                continue
            sell_from_acq = min(to_sell, vesting.currently_available)
            tax_scheme = plan.tax_scheme
            sales_fragment.append(RSUPortfolioSalesFragment(
                nb_stocks_sold=sell_from_acq,
                acq_date=vesting.vesting_date,
                unit_acquisition_price=vesting.acquisition_price_eur,
                tax_scheme=tax_scheme
            ))
            vesting.currently_available = vesting.currently_available - sell_from_acq
            to_sell -= sell_from_acq
            if to_sell == 0:
                break
        if to_sell > 0:
            print(f"WARNING: You are trying to sell more stocks than you have")
        rsu_portfolio_sale = RSUPortfolioSale(
            sale_id=sale_event.id,
            symbol=sale_event.symbol,
            sell_date=sale_event.sell_date,
            quantity=sale_event.quantity,
            sell_price=sale_event.sell_price,
            sell_currency=sale_event.sell_currency,
            fragments=sales_fragment,
            sell_price_eur=sell_price_eur
        )
        self.sales.append(rsu_portfolio_sale)
        return rsu_portfolio_sale

    def process_taxes(self, portfolio_sale: RSUPortfolioSale):
        helper = StockHelper()
        for f in portfolio_sale.fragments:
            helper.sell_rsus_2(
                symbol=portfolio_sale.symbol,
                nb_stocks_sold=f.nb_stocks_sold,
                acq_date=f.acq_date,
                unit_acquisition_price=f.unit_acquisition_price,
                sell_date=portfolio_sale.sell_date,
                sell_price_eur=portfolio_sale.sell_price_eur,
                tax_scheme=f.tax_scheme
            )
        agt = helper.compute_acquisition_gain_tax(portfolio_sale.sell_date.year)
        cgt = helper.compute_capital_gain_tax(portfolio_sale.sell_date.year)
        income_tax, social_tax = helper.estimate_tax(agt, cgt, 0.30)
        portfolio_sale.taxes = income_tax + social_tax
