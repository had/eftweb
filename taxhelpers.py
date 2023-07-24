from easyfrenchtax import TaxSimulator, StockHelper
from typing import List
from app.stocks import models as stock_models


def simulate_tax(year, tax_input):
    print("Using this input for tax: ", tax_input)
    tax_result = TaxSimulator(year, tax_input)
    return tax_result.state, tax_result.flags

def build_stock_helper(
        year: int,
        direct_stocks: List[stock_models.DirectStocks],
        dstock_sales_that_year: List[stock_models.DirectStocksSale],
        rsu_plans: List[stock_models.RSUPlan],
        rsu_vestings: List[stock_models.RSUVesting],
        rsu_sales_that_year: List[stock_models.RSUSale]):
    stock_helper = StockHelper()
    rsu_plans_dict = {}
    for ds in direct_stocks:
        print("Adding direct stocks", ds.symbol, ds.quantity, ds.acquisition_date, ds.acquisition_price, ds.stock_currency)
        stock_helper.add_espp(ds.symbol, ds.quantity, ds.acquisition_date, ds.acquisition_price, ds.stock_currency)
    for dss in dstock_sales_that_year:
        print("Adding direct stocks sale", dss.symbol, dss.quantity, dss.sell_date, dss.sell_price, dss.fees, dss.sell_currency)
        stock_helper.sell_espp(dss.symbol, dss.quantity, dss.sell_date, dss.sell_price, dss.fees, dss.sell_currency)
    for rp in rsu_plans:
        print("Adding RSU Plan", rp.name, rp.approval_date, rp.symbol, rp.stock_currency)
        stock_helper.rsu_plan(rp.name, rp.approval_date, rp.symbol, rp.stock_currency)
        rsu_plans_dict[rp.id] = rp
    for rv in rsu_vestings:
        plan = rsu_plans_dict[rv.rsu_plan_id]
        print("Adding RSU Vesting", rv.rsu_plan_id, rv.count, rv.vesting_date, rv.acquisition_price)
        stock_helper.rsu_vesting(plan.symbol, plan.name, rv.count, rv.vesting_date,
                                 rv.acquisition_price, plan.stock_currency)
    for rs in rsu_sales_that_year:
        print("Adding RSU sale", rs.symbol, rs.quantity, rs.sell_date, rs.sell_price, rs.fees, rs.sell_currency)
        stock_helper.sell_rsus(rs.symbol, rs.quantity, rs.sell_date, rs.sell_price, rs.fees, rs.sell_currency)
    return stock_helper

def taxed_stock_helper(
        year: int,
        direct_stocks: List[stock_models.DirectStocks],
        dstock_sales_that_year: List[stock_models.DirectStocksSale],
        rsu_plans: List[stock_models.RSUPlan],
        rsu_vestings: List[stock_models.RSUVesting],
        rsu_sales_that_year: List[stock_models.RSUSale]):
    stock_helper = build_stock_helper(
        year,
        direct_stocks,
        dstock_sales_that_year,
        rsu_plans,
        rsu_vestings,
        rsu_sales_that_year
    )
    agt = stock_helper.compute_acquisition_gain_tax(year)
    tax_report = stock_helper.compute_capital_gain_tax(year)
    tax_report["2042C"].update(agt)
    StockHelper.helper_capital_gain_tax(tax_report)
    return tax_report



