from easyfrenchtax import TaxSimulator, StockHelper
from typing import List
from app.stocks import models as stock_models


def simulate_tax(year, tax_input):
    print(tax_input)
    tax_result = TaxSimulator(year, tax_input)
    return tax_result.state, tax_result.flags

def taxed_stock_helper(direct_stocks: List[stock_models.DirectStocks], year: int, dstock_sales_that_year: List[
    stock_models.DirectStocksSale]):
    stock_helper = StockHelper()
    for ds in direct_stocks:
        print("Adding direct stocks", ds.taxpayer_owner, ds.symbol, ds.quantity, ds.acquisition_date, ds.acquisition_price, ds.stock_currency)
        stock_helper.add_espp(ds.taxpayer_owner, ds.symbol, ds.quantity, ds.acquisition_date, ds.acquisition_price, ds.stock_currency)
    for dss in dstock_sales_that_year:
        print("Adding direct stocks sale", dss.symbol, dss.quantity, dss.sell_date, dss.sell_price, dss.fees, dss.sell_currency)
        stock_helper.sell_espp(dss.symbol, dss.quantity, dss.sell_date, dss.sell_price, dss.fees, dss.sell_currency)
    agt = stock_helper.compute_acquisition_gain_tax(year)
    tax_report = stock_helper.compute_capital_gain_tax(year)
    tax_report["2042C"].update(agt)
    return tax_report



