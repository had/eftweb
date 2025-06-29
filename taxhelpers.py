from collections import namedtuple

from easyfrenchtax import TaxSimulator, StockHelper, StockType, TaxField
from typing import List
from app.stocks import models as stock_models
from app.tax.forms import *
from app.tax.models import *

StatementElement = namedtuple("StatementElement", ["name", "model", "form", "fields"])
statement_elements = [
   StatementElement("Income", IncomeSegment, IncomeForm, [
       ("Salary 1 (1AJ)", "salary_1_1AJ"),
       ("Salary 2 (1BJ)", "salary_2_1BJ")
   ]),
   StatementElement("Charity", CharitySegment, CharityForm, [
       ("Charity donation for people in distress (7UD)", "charity_donation_7UD"),
       ("Other charity donations (7UF)", "charity_donation_7UF")
   ]),
    StatementElement("Retirement investment", RetirementInvestmentSegment, RetirementInvestmentForm, [
        ("Investment on PER 1 (6NS)", "per_transfers_1_6NS"),
        ("Investment on PER 2 (6NT)", "per_transfers_2_6NT")
    ]),
    StatementElement("Service charges", ServicesChargesSegment, ServicesChargesForm, [
        ("Children care - 1st child (7GA)", "children_daycare_fees_7GA"),
        ("Home services (7DB)", "home_services_7DB")
    ]),
    StatementElement("Fixed income investment", FixedIncomeInvestmentSegment, FixedIncomeInvestmentForm, [
        ("Fixed income investments (2TR)", "fixed_income_interests_2TR"),
        ("Fixed income already taxed (2BH)", "fixed_income_interests_already_taxed_2BH"),
        ("Tax already paid on fixed income (2CK)", "interest_tax_already_paid_2CK")
    ]),
    StatementElement("Other investments", OtherInvestmentsSegment, OtherInvestmentsForm, [
        ("PME investment 1st period (7CF)", "pme_capital_subscription_7CF"),
        ("PME investment 2nd period (7CH)", "pme_capital_subscription_7CH"),
    ]),
    StatementElement("Shareholding", ShareholdingSegment, ShareholdingForm, [
        ("Taxable acquisition gain (1TZ)", "taxable_acquisition_gain_1TZ"),
        ("Acquisition gain rebates (1UZ)", "acquisition_gain_rebates_1UZ"),
        ("Acquisition gain 50% rebates (1WZ)", "acquisition_gain_50p_rebates_1WZ"),
        ("Other taxable gain 1 (1TT)", "exercise_gain_1_1TT"),
        ("Other taxable gain 2 (1UT)", "exercise_gain_2_1UT"),
        ("Capital gain (3VG)", "capital_gain_3VG"),
        ("Capital loss (3VH) *NOT IMPLEMENTED*", "capital_loss_3VH"),
    ]),
]

def prepare_tax_input(project, taxstatement):
    rendering_elements = []
    tax_input = {}
    for elt in statement_elements:
        elt_form = elt.form()
        elt_id = getattr(taxstatement, elt.name.lower().replace(' ','')+"_id")
        if elt_id:
            elt_object = elt.model.query.get(elt_id)
            for _, field in elt.fields:
                value = getattr(elt_object, field)
                getattr(elt_form, field).data = value
                field_names_fixups = {
                    'pme_capital_subscription_7CF': 'sme_capital_subscription_7CF',
                    'pme_capital_subscription_7CH': 'sme_capital_subscription_7CH'
                }
                tax_input[TaxField(field_names_fixups.get(field, field))] = value
        else:
            elt_object = None
        rendering_elements.append((elt.name, elt_object, elt_form, elt.fields, "upsert_"+elt.name.lower().replace(' ','')))
    tax_input[TaxField.MARRIED] = project.married
    tax_input[TaxField.NB_CHILDREN] = project.nb_children
    # TODO: set the proper birth years of children
    tax_input[TaxField.NB_CHILDREN_LT_6YO] = project.nb_children
    return tax_input, rendering_elements

def simulate_tax(year, tax_input):
    # print("Using this input for tax: ", tax_input)
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



