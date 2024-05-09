from easyfrenchtax import TaxSimulator, StockHelper, StockType
from typing import List
from app.stocks import models as stock_models


def simulate_tax(year, tax_input):
    print("Using this input for tax: ", tax_input)
    tax_result = TaxSimulator(year, tax_input, debug=True)
    return tax_result.state, tax_result.flags


def taxed_stock_helper(year: int, rsu_sales, stockoptions_sales, directstocks_sales):
    stock_helper = StockHelper()
    all_sales = ([(StockType.RSU, sale) for sale in rsu_sales]
                 + [(StockType.STOCKOPTIONS, sale) for sale in stockoptions_sales]
                 + [(StockType.ESPP, sale) for sale in directstocks_sales])
    all_sales.sort(key=lambda pf_sale: (pf_sale[1].sell_date, pf_sale[0]))

    for stock_type, pf_sale in all_sales:
        for f in pf_sale.fragments:
            match stock_type:
                case StockType.RSU:
                    stock_helper.sell_rsus(
                        symbol=pf_sale.symbol,
                        nb_stocks_sold=f.nb_stocks_sold,
                        acq_date=f.acq_date,
                        unit_acquisition_price=f.unit_acquisition_price,
                        sell_date=pf_sale.sell_date,
                        sell_price_eur=pf_sale.sell_price_eur,
                        tax_scheme=f.tax_scheme
                    )
                case StockType.STOCKOPTIONS:
                    stock_helper.sell_stockoptions(
                        symbol=pf_sale.symbol,
                        nb_stocks_sold=f.nb_stocks_sold,
                        unit_acquisition_price=f.unit_acquisition_price,
                        sell_date=pf_sale.sell_date,
                        sell_price_eur=pf_sale.sell_price_eur,
                        owner=pf_sale.owner
                    )
                case StockType.ESPP:
                    stock_helper.sell_espp(
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



