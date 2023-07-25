import pprint

import dateutil.relativedelta
from flask import render_template, redirect, url_for
from werkzeug.datastructures import FileStorage

import taxhelpers
from itertools import groupby
from sqlalchemy.exc import IntegrityError

from . import stocks
from .forms import DirectStocksForm, RsuPlanForm, RsuVestingForm, DirectStocksSaleForm, RsuImportForm, RsuSaleForm, \
    DirectStocksImportForm, StockOptionsImportForm
from .portfolio import RSUPortfolio, StockOptionsPortfolio, StockPortfolio
from .ticker import ticker
from .tsv_importer import import_rsu_tsv, import_dstocks_tsv, import_stockoptions_tsv
from .. import db
from ..main import models as main_models
from .models import DirectStocks, RSUPlan, RSUVesting, DirectStocksSale, RSUSale


@stocks.route("/project2/<int:project_id>/stocks", methods=["GET"])
def project_stocks_proto(project_id):
    project = main_models.Project.query.get(project_id)
    dstock_form = DirectStocksForm()
    rsuplan_form = RsuPlanForm()
    rsu_import_form = RsuImportForm()
    rsuvesting_form = RsuVestingForm()
    dstock_sale_form = DirectStocksSaleForm()
    rsu_sale_form = RsuSaleForm()

    rsu_portfolio = RSUPortfolio(project.id)
    rsu_plans = {
        symbol: {
            plan.name: (plan.tax_scheme.value, [
                (v.vesting_date, v.initial_amount, v.currently_available) for v in plan.vestings
            ]) for plan in plans}
        for symbol, plans in rsu_portfolio.plans.items()}
    stockoption_portfolio = StockOptionsPortfolio(project.id)
    stockoptions_plans = {
        symbol: {
            plan.name: (f"{plan.strike_price} {plan.currency}", [
                (v.vesting_date, v.initial_amount, v.currently_available) for v in plan.vestings
            ]) for plan in plans}
        for symbol, plans in stockoption_portfolio.plans.items()}

    directstocks_portfolio = StockPortfolio(project.id)
    directstocks = {
        symbol: [
            (s.acquisition_date, s.initial_amount, s.currently_available)
            for s in stocks
        ]
        for symbol, stocks in directstocks_portfolio.stocks.items()}

    symbols = set().union(rsu_plans.keys(), stockoptions_plans.keys(), directstocks.keys())
    symbols_stock = {symbol: ticker.get_stock_value(symbol) for symbol in symbols}

    # years = {ds.sell_date.year for ds in dstock_sales} | {rs.sell_date.year for rs in rsu_portfolio.sales}
    years = {}

    return render_template("project_stocks2.html",
                           project=project,
                           dstock_form=dstock_form,
                           rsuplan_form=rsuplan_form, rsu_import_form=rsu_import_form,
                           rsuvesting_form=rsuvesting_form,
                           dstock_sale_form=dstock_sale_form,
                           rsu_sale_form=rsu_sale_form,
                           sales_years=years, rsu_portfolio=rsu_portfolio,
                           symbols_stock=symbols_stock, rsu_plans=rsu_plans, stockoptions_plans=stockoptions_plans,
                           directstocks=directstocks
                           )


@stocks.route("/project/<int:project_id>/stocks", methods=["GET"])
def project_stocks(project_id):
    project = main_models.Project.query.get(project_id)
    dstock_form = DirectStocksForm()
    rsuplan_form = RsuPlanForm()
    rsu_import_form = RsuImportForm()
    directstocks_import_form = DirectStocksImportForm()
    stockoptions_import_form = StockOptionsImportForm()
    rsuvesting_form = RsuVestingForm()
    rsu_portfolio = RSUPortfolio(project.id)
    direct_stocks = DirectStocks.query.filter_by(project_id=project.id).all()
    direct_stocks_per_symbol = {symbol: list(ds) for symbol, ds in groupby(direct_stocks, key=lambda x: x.symbol)}
    dstock_sale_form = DirectStocksSaleForm()
    dstock_sales = DirectStocksSale.query.filter_by(project_id=project.id).all()
    rsu_sale_form = RsuSaleForm()
    years = {ds.sell_date.year for ds in dstock_sales} | {rs.sell_date.year for rs in rsu_portfolio.sales}
    return render_template("project_stocks.html",
                           project=project,
                           direct_stocks=direct_stocks_per_symbol, dstock_form=dstock_form,
                           rsuplan_form=rsuplan_form,
                           rsuvesting_form=rsuvesting_form,
                           dstock_sales=dstock_sales, dstock_sale_form=dstock_sale_form,
                           rsu_sale_form=rsu_sale_form,
                           rsu_import_form=rsu_import_form, directstocks_import_form=directstocks_import_form,
                           stockoptions_import_form=stockoptions_import_form,
                           sales_years=years, rsu_portfolio=rsu_portfolio
                           )


@stocks.route("/project/<int:project_id>/stocks/direct", methods=["POST"])
def add_direct_stocks(project_id):
    dstock_form = DirectStocksForm()
    if dstock_form.validate_on_submit():
        dstock = DirectStocks(
            project_id=project_id,
            taxpayer_owner=dstock_form.tp_owner.data,
            symbol=dstock_form.symbol.data,
            quantity=dstock_form.quantity.data,
            acquisition_date=dstock_form.acquisition_date.data,
            acquisition_price=dstock_form.acquisition_price.data,
            stock_currency=dstock_form.stock_currency.data
        )
        db.session.add(dstock)
        try:
            db.session.commit()
        except IntegrityError as e:
            print("ERR ", e)
            db.session.rollback()
        print("Added direct stocks:", dstock)
    else:
        # TODO: pop-up errors back to user?
        print("Validation error:", dstock_form.errors)
    return redirect(url_for('.project_stocks', project_id=project_id))


@stocks.route("/project/<int:project_id>/stocks/rsu", methods=["POST"])
def add_rsu_plan(project_id):
    rsuplan_form = RsuPlanForm()
    if rsuplan_form.validate_on_submit():
        rsuplan = RSUPlan(
            project_id=project_id,
            name=rsuplan_form.name.data,
            taxpayer_owner=rsuplan_form.tp_owner.data,
            approval_date=rsuplan_form.approval_date.data,
            symbol=rsuplan_form.symbol.data,
            stock_currency=rsuplan_form.stock_currency.data
        )
        try:
            db.session.add(rsuplan)
            db.session.commit()
        except IntegrityError as e:
            print("ERR ", e)
            db.session.rollback()
        print("Added rsu plan:", rsuplan)
    else:
        # TODO: pop-up errors back to user?
        print("Validation error:", rsuplan_form.errors)
    return redirect(url_for('.project_stocks', project_id=project_id))

@stocks.route("/project/<int:project_id>/stocks/rsu/import", methods=["POST"])
def import_rsu_plan(project_id):
    rsu_import_form = RsuImportForm()
    if rsu_import_form.validate_on_submit():
        rsuplan_file: FileStorage = rsu_import_form.tsv_file.data
        import_rsu_tsv(rsuplan_file, project_id)

    else:
        print(rsu_import_form.errors)
    return redirect(url_for('.project_stocks', project_id=project_id))

@stocks.route("/project/<int:project_id>/stocks/direct/import", methods=["POST"])
def import_dstocks(project_id):
    directstocks_import_form = DirectStocksImportForm()
    if directstocks_import_form.validate_on_submit():
        dstocks_file: FileStorage = directstocks_import_form.tsv_file.data
        import_dstocks_tsv(dstocks_file, project_id)
    else:
        print(directstocks_import_form.errors)
    return redirect(url_for('.project_stocks', project_id=project_id))

@stocks.route("/project/<int:project_id>/stocks/options/import", methods=["POST"])
def import_stockoptions(project_id):
    stockoptions_import_form = StockOptionsImportForm()
    if stockoptions_import_form.validate_on_submit():
        dstocks_file: FileStorage = stockoptions_import_form.tsv_file.data
        owner = stockoptions_import_form.tp_owner.data
        import_stockoptions_tsv(dstocks_file, owner, project_id)
    else:
        print(directstocks_import_form.errors)
    return redirect(url_for('.project_stocks', project_id=project_id))


@stocks.route("/project/<int:project_id>/stocks/rsu/vesting", methods=["POST"])
def add_rsu_vesting(project_id):
    rsuvesting_form = RsuVestingForm()
    if rsuvesting_form.validate_on_submit():
        rsuplan_id = rsuvesting_form.rsuplan_id.data
        periodicity = rsuvesting_form.periodicity.data
        qty = rsuvesting_form.quantity.data
        vdate = rsuvesting_form.vesting_date.data
        acq_price = rsuvesting_form.acquisition_price.data
        if periodicity == 'No':
            rsuvesting = RSUVesting(
                rsu_plan_id=rsuplan_id,
                count=qty,
                vesting_date=vdate,
                acquisition_price=acq_price
            )
            db.session.add(rsuvesting)
        else:
            delta = dateutil.relativedelta.relativedelta(months=+3 if periodicity == "Quarterly" else +1)
            for _ in range(rsuvesting_form.number_of_periods.data):
                rsuvesting = RSUVesting(
                    rsu_plan_id=rsuplan_id,
                    count=qty,
                    vesting_date=vdate,
                    acquisition_price=acq_price
                )
                db.session.add(rsuvesting)
                print(rsuvesting)
                vdate += delta
        db.session.commit()
    return redirect(url_for('.project_stocks', project_id=project_id))


@stocks.route("/project/<int:project_id>/stocks/direct/selling", methods=["POST"])
def add_dstocks_sale(project_id):
    dstock_sale_form = DirectStocksSaleForm()
    if dstock_sale_form.validate_on_submit():
        dstock_sale = DirectStocksSale(
            project_id=project_id,
            symbol=dstock_sale_form.symbol.data,
            quantity=dstock_sale_form.quantity.data,
            sell_date=dstock_sale_form.sell_date.data,
            sell_price=dstock_sale_form.sell_price.data,
            sell_currency=dstock_sale_form.sell_currency.data,
            fees=dstock_sale_form.fees.data
        )
        db.session.add(dstock_sale)
        try:
            db.session.commit()
        except IntegrityError as e:
            print("ERR ", e)
            db.session.rollback()
    else:
        # TODO: pop-up errors back to user?
        print("Validation error:", dstock_sale_form.errors)
    return redirect(url_for('.project_stocks', project_id=project_id))


@stocks.route("/project/<int:project_id>/stocks/rsu/selling", methods=["POST"])
def add_rsu_sale(project_id):
    rsu_sale_form = RsuSaleForm()
    if rsu_sale_form.validate_on_submit():
        rsu_sale = RSUSale(
            project_id=project_id,
            symbol=rsu_sale_form.symbol.data,
            quantity=rsu_sale_form.quantity.data,
            sell_date=rsu_sale_form.sell_date.data,
            sell_price=rsu_sale_form.sell_price.data,
            sell_currency=rsu_sale_form.sell_currency.data,
            fees=rsu_sale_form.fees.data
        )
        db.session.add(rsu_sale)
        try:
            db.session.commit()
        except IntegrityError as e:
            print("ERR ", e)
            db.session.rollback()
    else:
        # TODO: pop-up errors back to user?
        print("Validation error:", rsu_sale_form.errors)
    return redirect(url_for('.project_stocks', project_id=project_id))


# TODO: find a way to use a DELETE method instead of GET, this is not very nice and RESTful
@stocks.route("/project/<int:project_id>/stocks/direct/<int:dstocks_id>/delete")
def rm_direct_stocks(project_id, dstocks_id):
    DirectStocks.query.filter_by(id=dstocks_id).delete()
    db.session.commit()
    return redirect(url_for('.project_stocks', project_id=project_id))


@stocks.route("/project/<int:project_id>/stocks/rsu/<int:rsuplan_id>/delete")
def rm_rsu_plan(project_id, rsuplan_id):
    RSUVesting.query.filter_by(rsu_plan_id=rsuplan_id).delete()
    RSUPlan.query.filter_by(id=rsuplan_id).delete()
    db.session.commit()
    return redirect(url_for('.project_stocks', project_id=project_id))


@stocks.route("/project/<int:project_id>/stocks/rsu/dstock_sale/<int:dstock_sale_id>/delete")
def rm_dstock_sale(project_id, dstock_sale_id):
    DirectStocksSale.query.filter_by(id=dstock_sale_id).delete()
    db.session.commit()
    return redirect(url_for('.project_stocks', project_id=project_id))

@stocks.route("/project/<int:project_id>/stocks/rsu/rsu_sale/<int:rsu_sale_id>/delete")
def rm_rsu_sale(project_id, rsu_sale_id):
    RSUSale.query.filter_by(id=rsu_sale_id).delete()
    db.session.commit()
    return redirect(url_for('.project_stocks', project_id=project_id))


@stocks.route("/project/<int:project_id>/stocks/taxhelper/<int:year>")
def taxed_stock_helper(project_id, year):
    project = main_models.Project.query.get(project_id)
    direct_stocks = DirectStocks.query.filter_by(project_id=project.id).all()
    dstock_sales = DirectStocksSale.query.filter_by(project_id=project.id).all()
    dstock_sales_that_year = list(filter(lambda x: x.sell_date.year == year, dstock_sales))
    rsu_plans = RSUPlan.query.filter_by(project_id=project.id).all()
    rsu_plans_id = [p.id for p in rsu_plans]
    rsu_vestings = RSUVesting.query.filter(RSUVesting.rsu_plan_id.in_(rsu_plans_id)).all()
    rsu_sales = RSUSale.query.filter_by(project_id=project.id).all()
    for rs in rsu_sales:
        print("DEBUG1 ", rs.__dict__)
    rsu_sales_that_year = list(filter(lambda x: x.sell_date.year == year, rsu_sales))
    tax_report = taxhelpers.taxed_stock_helper(
        year,
        direct_stocks,
        dstock_sales_that_year,
        rsu_plans,
        rsu_vestings,
        rsu_sales_that_year
    )
    pretty_tax_report = pprint.pformat(tax_report)
    # taxhelpers.
    return render_template("stock_taxhelper.html", project=project, tax_report=pretty_tax_report, year=year)
