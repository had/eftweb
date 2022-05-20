import dateutil.relativedelta
from flask import render_template, redirect, url_for
import taxhelpers
from itertools import groupby
from sqlalchemy.exc import IntegrityError

from . import stocks
from .forms import DirectStocksForm, RsuPlanForm, RsuVestingForm, DirectStocksSaleForm
from .. import db
from ..main import models as main_models
from .models import DirectStocks, RSUPlan, RSUVesting, DirectStocksSale


@stocks.route("/project/<int:project_id>/stocks", methods=["GET"])
def project_stocks(project_id):
    project = main_models.Project.query.get(project_id)
    dstock_form = DirectStocksForm()
    rsuplan_form = RsuPlanForm()
    rsuvesting_form = RsuVestingForm()
    direct_stocks = DirectStocks.query.filter_by(project_id=project.id).all()
    direct_stocks_per_symbol = {symbol: list(ds) for symbol, ds in groupby(direct_stocks, key=lambda x: x.symbol)}
    rsu_plans = RSUPlan.query.filter_by(project_id=project.id).all()
    rsu_plans_id = [p.id for p in rsu_plans]
    rsu_vestings = RSUVesting.query.filter(RSUVesting.rsu_plan_id.in_(rsu_plans_id)).all()
    rsu_vestings_per_plan = {plan_id: list(v) for plan_id, v in groupby(rsu_vestings, key=lambda x: x.rsu_plan_id)}
    dstock_sale_form = DirectStocksSaleForm()
    dstock_sales = DirectStocksSale.query.filter_by(project_id=project.id).all()
    years = {ds.sell_date.year for ds in dstock_sales}
    print(years)
    return render_template("project_stocks.html",
                           project=project,
                           direct_stocks=direct_stocks_per_symbol, dstock_form=dstock_form,
                           rsu_plans=rsu_plans, rsuplan_form=rsuplan_form,
                           rsu_vestings=rsu_vestings_per_plan, rsuvesting_form=rsuvesting_form,
                           dstock_sales=dstock_sales, dstock_sale_form=dstock_sale_form,
                           sales_years=years
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
            grant_date=rsuplan_form.grant_date.data,
            symbol=rsuplan_form.symbol.data,
            stock_currency=rsuplan_form.stock_currency.data
        )
        db.session.add(rsuplan)
        try:
            db.session.commit()
        except IntegrityError as e:
            print("ERR ", e)
            db.session.rollback()
        print("Added rsu plan:", rsuplan)
    else:
        # TODO: pop-up errors back to user?
        print("Validation error:", rsuplan_form.errors)
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


@stocks.route("/project/<int:project_id>/stocks/taxhelper/<int:year>")
def taxed_stock_helper(project_id, year):
    project = main_models.Project.query.get(project_id)
    direct_stocks = DirectStocks.query.filter_by(project_id=project.id).all()
    # rsu_plans = models.RSUPlan.query.filter_by(project_id=project.id).all()
    # rsu_plans_id = [p.id for p in rsu_plans]
    # rsu_vestings = models.RSUVesting.query.filter(models.RSUVesting.rsu_plan_id.in_(rsu_plans_id)).all()
    dstock_sales = DirectStocksSale.query.filter_by(project_id=project.id).all()
    dstock_sales_that_year = filter(lambda x: x.sell_date.year == year, dstock_sales)
    tax_report = taxhelpers.taxed_stock_helper(direct_stocks, year, list(dstock_sales_that_year))
    print(tax_report)
    return render_template("stock_taxhelper.html", project=project, tax_report=tax_report, year=year)
