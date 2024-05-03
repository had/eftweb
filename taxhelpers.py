from easyfrenchtax import TaxSimulator, StockHelper
from typing import List
from app.stocks import models as stock_models


def simulate_tax(year, tax_input):
    print("Using this input for tax: ", tax_input)
    tax_result = TaxSimulator(year, tax_input, debug=True)
    return tax_result.state, tax_result.flags


def taxed_stock_helper(year: int, rsu_sales, stockoptions_sales, directstocks_sales):
    stock_helper = StockHelper()
    for pf_sale in rsu_sales:
        for f in pf_sale.fragments:
            stock_helper.sell_rsus_2(
                symbol=pf_sale.symbol,
                nb_stocks_sold=f.nb_stocks_sold,
                acq_date=f.acq_date,
                unit_acquisition_price=f.unit_acquisition_price,
                sell_date=pf_sale.sell_date,
                sell_price_eur=pf_sale.sell_price_eur,
                tax_scheme=f.tax_scheme
            )
    for pf_sale in stockoptions_sales:
        for f in pf_sale.fragments:
            stock_helper.sell_stockoptions_2(
                symbol=pf_sale.symbol,
                nb_stocks_sold=f.nb_stocks_sold,
                unit_acquisition_price=f.unit_acquisition_price,
                sell_date=pf_sale.sell_date,
                sell_price_eur=pf_sale.sell_price_eur,
                owner=pf_sale.owner
            )
    for pf_sale in directstocks_sales:
        for f in pf_sale.fragments:
            stock_helper.sell_espp_2(
                symbol=pf_sale.symbol,
                nb_stocks_sold=f.nb_stocks_sold,
                unit_acquisition_price=f.unit_acquisition_price,
                sell_date=pf_sale.sell_date,
                sell_price_eur=pf_sale.sell_price_eur,
            )
    agt = stock_helper.compute_acquisition_gain_tax(year)
    tax_report = stock_helper.compute_capital_gain_tax(year)
    tax_report["2042C"].update(agt)
    StockHelper.helper_capital_gain_tax(tax_report)
    return tax_report



