import pprint
from datetime import date

import dateutil.relativedelta
from flask import render_template, redirect, url_for, request
from werkzeug.datastructures import FileStorage

import taxhelpers
from sqlalchemy.exc import IntegrityError

from . import stocks
from .forms import DirectStocksForm, RsuImportForm, DirectStocksImportForm, StockOptionsImportForm, SaleForm, \
    SellEventsImportForm
from .portfolio import RSUPortfolio, StockOptionsPortfolio, StockPortfolio, PortfolioRsuPlan, PortfolioDirectStockPlan
from .ticker import ticker
from .tsv_importer import import_rsu_tsv, import_dstocks_tsv, import_stockoptions_tsv, \
    import_etrade_sell_events_tsv
from .. import db
from ..main import models as main_models
from .models import DirectStocks, RSUPlan, RSUVesting, DirectStocksSale, RSUSale, StockOptionVesting, StockOptionPlan, \
    SaleEvent, DirectStocksPlan


@stocks.app_template_filter()
def sales_to_tooltip(sales):
    html_list = []
    for s in sales[:3]:
        html_list.append(f"{s.sell_date} : {s.quantity} x {s.sell_price} {s.sell_currency} <br> => net €{round(s.sell_price_eur*s.quantity-s.taxes, 2)}")
    return "<ul class='p-0'><li>" + "</li><li>".join(html_list) + "</li></ul>"

@stocks.app_template_filter()
def plans_to_available_stocks(plans):
    available_stocks = 0
    for p in plans:
        if isinstance(p, PortfolioDirectStockPlan):
            for s in p.stocks:
                available_stocks += s.currently_available
        else:
            for v in p.vestings:
                if v.vesting_date <= date.today():
                    available_stocks += v.currently_available
    return available_stocks

@stocks.route("/project/<int:project_id>/stocks", methods=["GET"])
def project_stocks(project_id):
    project = main_models.Project.query.get(project_id)
    dstock_form = DirectStocksForm()
    rsu_import_form = RsuImportForm()
    directstocks_import_form = DirectStocksImportForm()
    stockoptions_import_form = StockOptionsImportForm()
    sale_form = SaleForm()
    sale_form.sell_date.data = date.today()
    sell_events_import_form = SellEventsImportForm()

    rsu_portfolio = RSUPortfolio(project_id)
    rsu_plans = rsu_portfolio.plans

    stockoption_portfolio = StockOptionsPortfolio(project_id)
    stockoptions_plans = stockoption_portfolio.plans

    directstocks_portfolio = StockPortfolio(project_id)
    directstocks_plans = directstocks_portfolio.plans

    symbols = set().union(rsu_plans.keys(), stockoptions_plans.keys(), directstocks_plans.keys())
    symbols_stock = {symbol: ticker.get_stock_value(symbol) for symbol in symbols}

    years = rsu_portfolio.get_years() | stockoption_portfolio.get_years() | directstocks_portfolio.get_years()

    sales = {
        "RSU": rsu_portfolio.sales,
        "STOCKOPTIONS": stockoption_portfolio.sales,
        "DIRECTSTOCKS": directstocks_portfolio.sales
    }

    return render_template("project_stocks.html",
                           project=project,
                           dstock_form=dstock_form,
                           rsu_import_form=rsu_import_form, directstocks_import_form=directstocks_import_form,
                           stockoptions_import_form=stockoptions_import_form, sale_form=sale_form,
                           sell_events_import_form=sell_events_import_form,
                           sales_years=years, symbols_stock=symbols_stock,
                           rsu_plans=rsu_plans, stockoptions_plans=stockoptions_plans,
                           directstocks_plans=directstocks_plans,
                           sales=sales
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
        print(stockoptions_import_form.errors)
    return redirect(url_for('.project_stocks', project_id=project_id))

@stocks.route("/project/<int:project_id>/stocks/sell/import", methods=["POST"])
def import_sell_events(project_id):
    sell_events_import_form = SellEventsImportForm()
    if sell_events_import_form.validate_on_submit():
        sell_events_file: FileStorage = sell_events_import_form.tsv_file.data
        print("Loading Sell Events from " + sell_events_file.name)
        import_etrade_sell_events_tsv(sell_events_file, project_id)
    else:
        print(sell_events_import_form.errors)
    return redirect(url_for('.project_stocks', project_id=project_id))

@stocks.route("/project/<int:project_id>/stocks/sell", methods=["POST"])
def sell_stocks(project_id):
    sale_form = SaleForm()
    if sale_form.validate_on_submit():
        sale = SaleEvent(
            project_id=project_id,
            type=sale_form.stock_type.data,
            symbol=sale_form.symbol.data,
            quantity=sale_form.quantity.data,
            sell_date=sale_form.sell_date.data,
            sell_price=sale_form.sell_price.data,
            sell_currency=sale_form.sell_currency.data,
            fees=0
        )
        db.session.add(sale)
        try:
            db.session.commit()
        except IntegrityError as e:
            print("ERR ", e)
            db.session.rollback()
    else:
        print(sale_form.sell_date.data)
        # TODO: pop-up errors back to user?
        print("Validation error:", sale_form.errors)
    return redirect(url_for('.project_stocks', project_id=project_id))


# TODO: find a way to use a DELETE method instead of GET, this is not very nice and RESTful
@stocks.route("/project/<int:project_id>/stocks/direct/<int:dsplan_id>/delete")
def rm_dstock_plan(project_id, dsplan_id):
    DirectStocks.query.filter_by(direct_stocks_plan_id=dsplan_id).delete()
    DirectStocksPlan.query.filter_by(id=dsplan_id).delete()
    db.session.commit()
    return redirect(url_for('.project_stocks', project_id=project_id))


@stocks.route("/project/<int:project_id>/stocks/rsu/<int:rsuplan_id>/delete")
def rm_rsu_plan(project_id, rsuplan_id):
    RSUVesting.query.filter_by(rsu_plan_id=rsuplan_id).delete()
    RSUPlan.query.filter_by(id=rsuplan_id).delete()
    db.session.commit()
    return redirect(url_for('.project_stocks', project_id=project_id))


@stocks.route("/project/<int:project_id>/stocks/options/<int:stockoption_plan_id>/delete")
def rm_stockoptions_plan(project_id, stockoption_plan_id):
    StockOptionVesting.query.filter_by(stockoption_plan_id=stockoption_plan_id).delete()
    StockOptionPlan.query.filter_by(id=stockoption_plan_id).delete()
    db.session.commit()
    return redirect(url_for('.project_stocks', project_id=project_id))

@stocks.route("/project/<int:project_id>/stocks/sell/delete")
def rm_sell_event(project_id):
    sale_id = request.args.get("id")
    SaleEvent.query.filter_by(id=sale_id).delete()
    db.session.commit()
    return redirect(url_for('.project_stocks', project_id=project_id))

@stocks.route("/project/<int:project_id>/stocks/taxhelper/<int:year>")
def taxed_stock_helper(project_id, year):
    project = main_models.Project.query.get(project_id)
    rsu_portfolio = RSUPortfolio(project.id)
    rsu_sales = [pf_sale
                 for sales in rsu_portfolio.sales.values()
                 for pf_sale in sales
                 if pf_sale.sell_date.year == year]
    stockoption_portfolio = StockOptionsPortfolio(project.id)
    stockoptions_sales = [pf_sale
                          for sales in stockoption_portfolio.sales.values()
                          for pf_sale in sales
                          if pf_sale.sell_date.year == year]
    directstocks_portfolio = StockPortfolio(project.id)
    directstocks_sales = [pf_sale
                          for sales in directstocks_portfolio.sales.values()
                          for pf_sale in sales
                          if pf_sale.sell_date.year == year]

    tax_report = taxhelpers.taxed_stock_helper(year, rsu_sales, stockoptions_sales, directstocks_sales)
    form_2042C = pprint.pformat(tax_report['2042C'])
    form_2074 = []
    for title_2074 in tax_report['2074']:
        title = []
        for field, value in title_2074.items():
            field_id = field.split('_')[-1]
            field_name = ' '.join(field.split('_')[:-1]).capitalize()
            title.append((field_id, field_name, value))
        form_2074.append(title)
    print(form_2074)

    return render_template("stock_taxhelper.html",
                           project=project,
                           form_2042C=form_2042C,
                           form_2074=form_2074,
                           year=year)
