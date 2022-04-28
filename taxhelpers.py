from easyfrenchtax import TaxSimulator, StockHelper
from typing import List, Set, Dict, Tuple, Optional
import models


def simulate_tax(year, elements):
    print(elements)
    income = elements["Income"]
    charity = elements["Charity"]
    tax_input = {
        "household_shares": 2,
        "nb_kids": 0,
        "salary_1_1AJ": income.income_1 if income else 0,
        "salary_2_1BJ": income.income_2 if income else 0,
        "charity_donation_7UD": charity.charity_7UD if charity else 0,
        "charity_donation_7UF": charity.charity_7UF if charity else 0
    }
    tax_result = TaxSimulator(year, tax_input).state
    return tax_result

def taxed_stock_helper(direct_stocks: List[models.DirectStocks], year: int, dstock_sales_that_year: List[models.DirectStocksSale]):
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



