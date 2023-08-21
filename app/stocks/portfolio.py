from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import DefaultDict, Optional

from currency_converter import CurrencyConverter

from easyfrenchtax import StockHelper, RsuTaxScheme, StockType

from app.stocks.models import RSUPlan, RSUVesting, StockOptionPlan, StockOptionVesting, DirectStocks, SaleEvent, \
    DirectStocksPlan
from app.stocks.ticker import ticker


@dataclass
class PortfolioSalesFragment:
    nb_stocks_sold: int
    acq_date: date
    unit_acquisition_price: float
    tax_scheme: Optional[RsuTaxScheme] = None


@dataclass
class PortfolioSale:
    sale_id: int
    symbol: str
    sell_date: date
    quantity: int
    sell_price: float
    sell_currency: str
    fragments: list[PortfolioSalesFragment]
    sell_price_eur: float
    taxes: Optional[int] = None
    owner: Optional[int] = None


@dataclass
class PortfolioRsuVesting:
    vesting_date: date
    initial_amount: int
    currently_available: int
    acquisition_price_eur: float


@dataclass
class   PortfolioRsuPlan:
    plan_id: int
    name: str
    symbol: str
    tax_scheme: RsuTaxScheme
    vestings: list[PortfolioRsuVesting]


cc = CurrencyConverter(fallback_on_wrong_date=True, fallback_on_missing_rate=True)


class RSUPortfolio:
    plans: DefaultDict[str, list[PortfolioRsuPlan]]
    sales: DefaultDict[str, list[PortfolioSale]]

    def __init__(self, project_id: int):
        # currency converter (USD/EUR in particular)
        raw_plans = RSUPlan.query.filter_by(project_id=project_id).all()
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
                    acquisition_price_eur=cc.convert(v.acquisition_price, p.stock_currency, "EUR")
                ) for v in vestings]))
        raw_sales = SaleEvent.query.filter_by(project_id=project_id, type=StockType.RSU).all()
        self.sales = defaultdict(list)
        for s in raw_sales:
            portfolio_sale = self.process_sale(s)
            self.process_taxes(portfolio_sale)

    def get_years(self) -> set[int]:
        return {s.sell_date.year for sl in self.sales.values() for s in sl}

    def process_sale(self, sale_event: SaleEvent):
        sell_date = sale_event.sell_date
        sell_price_eur = round(
            cc.convert(sale_event.sell_price, sale_event.sell_currency.upper(), "EUR", date=sell_date), 2)
        to_sell = sale_event.quantity

        # Acquisitions are sorted by date, this is the rule set by the tax office (FIFO, or PEPS="premier entré premier
        # sorti"); we only keep stocks acquired *before* the sell date, in case we input a sell event in the middle of
        # acquisitions.
        rsu_before_sell_date = sorted(
            [(p, r) for p in self.plans[sale_event.symbol] for r in p.vestings if r.vesting_date < sell_date],
            key=lambda pr: pr[1].vesting_date
        )

        sales_fragment = []
        for plan, vesting in rsu_before_sell_date:
            if vesting.currently_available == 0:
                continue
            sell_from_acq = min(to_sell, vesting.currently_available)
            tax_scheme = plan.tax_scheme
            sales_fragment.append(PortfolioSalesFragment(
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
        rsu_portfolio_sale = PortfolioSale(
            sale_id=sale_event.id,
            symbol=sale_event.symbol,
            sell_date=sale_event.sell_date,
            quantity=sale_event.quantity,
            sell_price=sale_event.sell_price,
            sell_currency=sale_event.sell_currency,
            fragments=sales_fragment,
            sell_price_eur=sell_price_eur
        )
        self.sales[sale_event.symbol].append(rsu_portfolio_sale)
        return rsu_portfolio_sale

    def process_taxes(self, portfolio_sale: PortfolioSale):
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
        income_tax, social_tax = helper.estimate_tax(agt, cgt, 0.41)
        portfolio_sale.taxes = income_tax + social_tax

    def tax_helper(self, helper: StockHelper):
        for sales in self.sales.values():
            for pf_sale in sales:
                for f in pf_sale.fragments:
                    helper.sell_rsus_2(
                        symbol=pf_sale.symbol,
                        nb_stocks_sold=f.nb_stocks_sold,
                        acq_date=f.acq_date,
                        unit_acquisition_price=f.unit_acquisition_price,
                        sell_date=pf_sale.sell_date,
                        sell_price_eur=pf_sale.sell_price_eur,
                        tax_scheme=f.tax_scheme
                    )


@dataclass
class PortfolioStockOptionVesting:
    vesting_date: date
    initial_amount: int
    currently_available: int


@dataclass
class PortfolioStockOptionPlan:
    plan_id: int
    name: str
    symbol: str
    owner: int
    strike_price: float
    currency: str
    vestings: list[PortfolioStockOptionVesting]


class StockOptionsPortfolio:
    plans: DefaultDict[str, list[PortfolioStockOptionPlan]]
    sales: DefaultDict[str, list[PortfolioSale]]

    def __init__(self, project_id: int):
        raw_plans = StockOptionPlan.query.filter_by(project_id=project_id).all()
        self.plans = defaultdict(list)
        for p in raw_plans:
            vestings = StockOptionVesting.query.filter_by(stockoption_plan_id=p.id).all()
            self.plans[p.symbol].append(PortfolioStockOptionPlan(
                plan_id=p.id,
                name=p.name,
                symbol=p.symbol,
                owner=p.taxpayer_owner,
                strike_price=p.strike_price,
                currency=p.stock_currency,
                vestings=[PortfolioStockOptionVesting(
                    vesting_date=v.vesting_date,
                    initial_amount=v.count,
                    currently_available=v.count,
                ) for v in vestings]))
        raw_sales = SaleEvent.query.filter_by(project_id=project_id, type=StockType.STOCKOPTIONS).all()
        self.sales = defaultdict(list)
        for s in raw_sales:
            portfolio_sale = self.process_sale(s)
            self.process_taxes(portfolio_sale)

    def get_years(self) -> set[int]:
        return {s.sell_date.year for sl in self.sales.values() for s in sl}

    def process_sale(self, sale_event: SaleEvent):
        sell_date = sale_event.sell_date
        sell_price_eur = round(
            cc.convert(sale_event.sell_price, sale_event.sell_currency.upper(), "EUR", date=sell_date), 2)
        to_sell = sale_event.quantity
        # Note: we assume there's only 1 owner when selling for a particular symbol; so we'll take the owner declared in the last plan used
        last_owner = 0

        so_before_sell_date = sorted(
            [(p, v) for p in self.plans[sale_event.symbol] for v in p.vestings if v.vesting_date < sell_date],
            key=lambda pv: pv[1].vesting_date
        )

        sales_fragment = []
        for plan, vesting in so_before_sell_date:
            if vesting.currently_available == 0:
                continue
            sell_from_acq = min(to_sell, vesting.currently_available)
            sales_fragment.append(PortfolioSalesFragment(
                nb_stocks_sold=sell_from_acq,
                acq_date=vesting.vesting_date,
                unit_acquisition_price=round(
                    cc.convert(plan.strike_price, plan.currency.upper(), "EUR", date=sell_date), 2)
            ))
            vesting.currently_available = vesting.currently_available - sell_from_acq
            to_sell -= sell_from_acq
            last_owner = plan.owner
            if to_sell == 0:
                break

        if to_sell > 0:
            print(f"WARNING: You are trying to sell more stocks than you have")
        so_portfolio_sale = PortfolioSale(
            sale_id=sale_event.id,
            symbol=sale_event.symbol,
            sell_date=sale_event.sell_date,
            quantity=sale_event.quantity,
            sell_price=sale_event.sell_price,
            sell_currency=sale_event.sell_currency,
            fragments=sales_fragment,
            sell_price_eur=sell_price_eur,
            owner=last_owner
        )
        self.sales[sale_event.symbol].append(so_portfolio_sale)
        return so_portfolio_sale

    def process_taxes(self, portfolio_sale: PortfolioSale):
        helper = StockHelper()
        for f in portfolio_sale.fragments:
            helper.sell_stockoptions_2(
                symbol=portfolio_sale.symbol,
                nb_stocks_sold=f.nb_stocks_sold,
                unit_acquisition_price=f.unit_acquisition_price,
                sell_date=portfolio_sale.sell_date,
                sell_price_eur=portfolio_sale.sell_price_eur,
                owner=portfolio_sale.owner
            )
        agt = helper.compute_acquisition_gain_tax(portfolio_sale.sell_date.year)
        cgt = helper.compute_capital_gain_tax(portfolio_sale.sell_date.year)
        income_tax, social_tax = helper.estimate_tax(agt, cgt, 0.41)
        portfolio_sale.taxes = income_tax + social_tax


@dataclass
class PortfolioDirectStock:
    acquisition_date: date
    acquisition_price: float
    initial_amount: int
    currently_available: int

@dataclass
class PortfolioDirectStockPlan:
    plan_id: int
    name: str
    symbol: str
    currency: str
    stocks: list[PortfolioDirectStock]


class StockPortfolio:
    plans: DefaultDict[str, list[PortfolioDirectStockPlan]]
    sales: DefaultDict[str, list[PortfolioSale]]

    def __init__(self, project_id: int):
        raw_plans = DirectStocksPlan.query.filter_by(project_id=project_id).all()
        self.plans = defaultdict(list)
        for p in raw_plans:
            stocks = DirectStocks.query.filter_by(direct_stocks_plan_id=p.id).all()
            self.plans[p.symbol].append(PortfolioDirectStockPlan(
                plan_id=p.id,
                name=p.name,
                symbol=p.symbol,
                currency=p.stock_currency,
                stocks=[PortfolioDirectStock(
                    acquisition_date=s.acquisition_date,
                    acquisition_price=s.acquisition_price,
                    initial_amount=s.quantity,
                    currently_available=s.quantity
                ) for s in stocks]))
        raw_sales = SaleEvent.query.filter_by(project_id=project_id, type=StockType.ESPP).all()
        self.sales = defaultdict(list)
        for s in raw_sales:
            portfolio_sale = self.process_sale(s)
            self.process_taxes(portfolio_sale)

    def get_years(self) -> set[int]:
        return {s.sell_date.year for sl in self.sales.values() for s in sl}

    def process_sale(self, sale_event: SaleEvent):
        sell_date = sale_event.sell_date
        sell_price_eur = round(
            cc.convert(sale_event.sell_price, sale_event.sell_currency.upper(), "EUR", date=sell_date), 2)
        to_sell = sale_event.quantity

        # Acquisitions are sorted by date
        ds_before_sell_date = sorted(
            [s for p in self.plans[sale_event.symbol] for s in p.stocks if s.acquisition_date < sell_date],
            key=lambda s: s.acquisition_date
        )
        sales_fragment = []
        for ds in ds_before_sell_date:
            if ds.currently_available == 0:
                continue
            sell_from_acq = min(to_sell, ds.currently_available)
            sales_fragment.append(PortfolioSalesFragment(
                nb_stocks_sold=sell_from_acq,
                acq_date=ds.acquisition_date,
                unit_acquisition_price=ds.acquisition_price,
            ))
            ds.currently_available = ds.currently_available - sell_from_acq
            to_sell -= sell_from_acq
            if to_sell == 0:
                break
        if to_sell > 0:
            print(f"WARNING: You are trying to sell more stocks than you have")
        ds_portfolio_sale = PortfolioSale(
            sale_id=sale_event.id,
            symbol=sale_event.symbol,
            sell_date=sale_event.sell_date,
            quantity=sale_event.quantity,
            sell_price=sale_event.sell_price,
            sell_currency=sale_event.sell_currency,
            fragments=sales_fragment,
            sell_price_eur=sell_price_eur
        )
        self.sales[sale_event.symbol].append(ds_portfolio_sale)
        return ds_portfolio_sale

    def process_taxes(self, portfolio_sale: PortfolioSale):
        helper = StockHelper()
        for f in portfolio_sale.fragments:
            helper.sell_espp_2(
                symbol=portfolio_sale.symbol,
                nb_stocks_sold=f.nb_stocks_sold,
                unit_acquisition_price=f.unit_acquisition_price,
                sell_date=portfolio_sale.sell_date,
                sell_price_eur=portfolio_sale.sell_price_eur,
            )
        agt = helper.compute_acquisition_gain_tax(portfolio_sale.sell_date.year)
        cgt = helper.compute_capital_gain_tax(portfolio_sale.sell_date.year)
        income_tax, social_tax = helper.estimate_tax(agt, cgt, 0.41)
        portfolio_sale.taxes = income_tax + social_tax
