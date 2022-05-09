import datetime

import dateutil.relativedelta
from flask import render_template, redirect, session, url_for, flash
import forms
import models
import taxhelpers
from app import app, db
from collections import namedtuple
from itertools import groupby

@app.route("/", methods=["GET", "POST"])
def index():
    form = forms.ProjectForm()
    if form.validate_on_submit():
        project = models.Project(
            name=form.name.data
        )
        db.session.add(project)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        flash(f"Project added (total {len(models.Project.query.all())} projects)")
        return redirect(url_for('project_tax', project_id=project.id))
    projects = models.Project.query.all()
    return render_template("index.html", name="Guest", projects=projects, form=form)

@app.route("/project/<int:project_id>", methods=["GET", "POST"])
def project_tax(project_id):
    project = models.Project.query.get(project_id)
    # prepare project form in case of edit/update
    project_form = forms.ProjectForm()
    project_form.name.data = project.name
    project_form.situation.data = "Married" if project.married else "Single"
    project_form.nb_children.data = project.nb_children
    # tax form
    tax_form = forms.TaxStatementForm()
    if tax_form.validate_on_submit():
        taxstatement = models.TaxStatement(project_id=project_id, year=tax_form.year.data)
        db.session.add(taxstatement)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        flash(f"Tax statement added")
        return redirect(url_for('project_tax', project_id=project.id))
    else:
        # prefill with current year
        tax_form.year.data = datetime.date.today().year
    statements = models.TaxStatement.query.filter_by(project_id=project.id).all()
    return render_template("project_tax.html", project=project, tax_form=tax_form, project_edit_from=project_form, taxstatements=statements)

@app.route("/project/<int:project_id>/edit", methods=["POST"])
def project_update(project_id):
    form = forms.ProjectForm()
    if form.validate_on_submit():
        project = models.Project(
            name=form.name.data
        )
        project = models.Project.query.get(project_id)
        project.name = form.name.data
        project.married = (form.situation.data == "Married")
        project.nb_children = form.nb_children.data
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    else:
        # TODO: show validation to user
        print("Validation error")
    return redirect(url_for('project_tax', project_id=project.id))


@app.route("/project/<int:project_id>/delete", methods=["GET", "POST"])
def project_delete(project_id):
    project = models.Project.query.get(project_id)
    db.session.delete(project)
    db.session.commit()
    return redirect(url_for("index"))

###### Stocks ######

@app.route("/project/<int:project_id>/stocks", methods=["GET"])
def project_stocks(project_id):
    project = models.Project.query.get(project_id)
    dstock_form = forms.DirectStocksForm()
    rsuplan_form = forms.RsuPlanForm()
    rsuvesting_form = forms.RsuVestingForm()
    direct_stocks = models.DirectStocks.query.filter_by(project_id=project.id).all()
    direct_stocks_per_symbol = {symbol:list(ds) for symbol, ds in groupby(direct_stocks, key=lambda x:x.symbol)}
    rsu_plans = models.RSUPlan.query.filter_by(project_id=project.id).all()
    rsu_plans_id = [p.id for p in rsu_plans]
    rsu_vestings = models.RSUVesting.query.filter(models.RSUVesting.rsu_plan_id.in_(rsu_plans_id)).all()
    rsu_vestings_per_plan = {plan_id:list(v) for plan_id,v in groupby(rsu_vestings, key=lambda x:x.rsu_plan_id)}
    dstock_sale_form = forms.DirectStocksSaleForm()
    dstock_sales = models.DirectStocksSale.query.filter_by(project_id=project.id).all()
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

@app.route("/project/<int:project_id>/stocks/direct", methods=["POST"])
def add_direct_stocks(project_id):
    dstock_form = forms.DirectStocksForm()
    if dstock_form.validate_on_submit():
        dstock = models.DirectStocks(
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
    return redirect(url_for('project_stocks', project_id=project_id))

@app.route("/project/<int:project_id>/stocks/rsu", methods=["POST"])
def add_rsu_plan(project_id):
    rsuplan_form = forms.RsuPlanForm()
    if rsuplan_form.validate_on_submit():
        rsuplan = models.RSUPlan(
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
    return redirect(url_for('project_stocks', project_id=project_id))

@app.route("/project/<int:project_id>/stocks/rsu/vesting", methods=["POST"])
def add_rsu_vesting(project_id):
    rsuvesting_form = forms.RsuVestingForm()
    if rsuvesting_form.validate_on_submit():
        rsuplan_id = rsuvesting_form.rsuplan_id.data
        periodicity = rsuvesting_form.periodicity.data
        qty = rsuvesting_form.quantity.data
        vdate = rsuvesting_form.vesting_date.data
        acq_price = rsuvesting_form.acquisition_price.data
        if periodicity == 'No':
            rsuvesting = models.RSUVesting(
                rsu_plan_id=rsuplan_id,
                count=qty,
                vesting_date=vdate,
                acquisition_price=acq_price
            )
            db.session.add(rsuvesting)
        else:
            delta = dateutil.relativedelta.relativedelta(months= +3 if periodicity == "Quarterly" else +1)
            for _ in range(rsuvesting_form.number_of_periods.data):
                rsuvesting = models.RSUVesting(
                    rsu_plan_id=rsuplan_id,
                    count=qty,
                    vesting_date=vdate,
                    acquisition_price=acq_price
                )
                db.session.add(rsuvesting)
                print(rsuvesting)
                vdate += delta
        db.session.commit()
    return redirect(url_for('project_stocks', project_id=project_id))

@app.route("/project/<int:project_id>/stocks/direct/selling", methods=["POST"])
def add_dstocks_sale(project_id):
    dstock_sale_form = forms.DirectStocksSaleForm()
    if dstock_sale_form.validate_on_submit():
        dstock_sale = models.DirectStocksSale(
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
    return redirect(url_for('project_stocks', project_id=project_id))

# TODO: find a way to use a DELETE method instead of GET, this is not very nice and RESTful
@app.route("/project/<int:project_id>/stocks/direct/<int:dstocks_id>/delete")
def rm_direct_stocks(project_id, dstocks_id):
    models.DirectStocks.query.filter_by(id=dstocks_id).delete()
    db.session.commit()
    return redirect(url_for('project_stocks', project_id=project_id))

@app.route("/project/<int:project_id>/stocks/rsu/<int:rsuplan_id>/delete")
def rm_rsu_plan(project_id, rsuplan_id):
    models.RSUVesting.query.filter_by(rsu_plan_id=rsuplan_id).delete()
    models.RSUPlan.query.filter_by(id=rsuplan_id).delete()
    db.session.commit()
    return redirect(url_for('project_stocks', project_id=project_id))

@app.route("/project/<int:project_id>/stocks/rsu/dstock_sale/<int:dstock_sale_id>/delete")
def rm_dstock_sale(project_id, dstock_sale_id):
    models.DirectStocksSale.query.filter_by(id=dstock_sale_id).delete()
    db.session.commit()
    return redirect(url_for('project_stocks', project_id=project_id))

@app.route("/project/<int:project_id>/stocks/taxhelper/<int:year>")
def taxed_stock_helper(project_id, year):
    project = models.Project.query.get(project_id)
    direct_stocks = models.DirectStocks.query.filter_by(project_id=project.id).all()
    # rsu_plans = models.RSUPlan.query.filter_by(project_id=project.id).all()
    # rsu_plans_id = [p.id for p in rsu_plans]
    # rsu_vestings = models.RSUVesting.query.filter(models.RSUVesting.rsu_plan_id.in_(rsu_plans_id)).all()
    dstock_sales = models.DirectStocksSale.query.filter_by(project_id=project.id).all()
    dstock_sales_that_year = filter(lambda x: x.sell_date.year == year, dstock_sales)
    tax_report = taxhelpers.taxed_stock_helper(direct_stocks, year, dstock_sales_that_year)
    print(tax_report)
    return render_template("stock_taxhelper.html", project=project, tax_report=tax_report, year=year)


###### Tax statements ######

@app.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>/delete", methods=["GET", "POST"])
def taxstatement_delete(project_id, taxstatement_id):
    taxstatement = models.TaxStatement.query.get(taxstatement_id)
    db.session.delete(taxstatement)
    db.session.commit()
    return redirect(url_for("project_tax", project_id=project_id))

StatementElement = namedtuple("StatementElement", ["name", "model", "form", "fields"])
statement_elements = [
   StatementElement("Income", models.IncomeSegment, forms.IncomeForm, [
       ("Salary 1 (1AJ)", "salary_1_1AJ"),
       ("Salary 2 (1BJ)", "salary_2_1BJ")
   ]),
   StatementElement("Charity", models.CharitySegment, forms.CharityForm, [
       ("Charity donation for people in distress (7UD)", "charity_donation_7UD"),
       ("Other charity donations (7UF)", "charity_donation_7UF")
   ]),
    StatementElement("Retirement investment", models.RetirementInvestmentSegment, forms.RetirementInvestmentForm, [
        ("Investment on PER 1 (6NS)", "per_transfers_1_6NS"),
        ("Investment on PER 2 (6NT)", "per_transfers_2_6NT")
    ]),
    StatementElement("Service charges", models.ServicesChargesSegment, forms.ServicesChargesForm, [
        ("Children care - 1st child (7GA)", "children_daycare_fees_7GA"),
        ("Home services (7DB)", "home_services_7DB")
    ]),
    StatementElement("Fixed income investment", models.FixedIncomeInvestmentSegment, forms.FixedIncomeInvestmentForm, [
        ("Fixed income investments (2TR)", "fixed_income_interests_2TR"),
        ("Fixed income already taxed (2BH)", "fixed_income_interests_already_taxed_2BH"),
        ("Tax already paid on fixed income (2CK)", "interest_tax_already_paid_2CK")
    ]),
    StatementElement("Other investments", models.OtherInvestmentsSegment, forms.OtherInvestmentsForm, [
        ("PME investment 1st period (7CF)", "pme_capital_subscription_7CF"),
        ("PME investment 2nd period (7CH)", "pme_capital_subscription_7CH"),
    ]),
    StatementElement("Shareholding", models.ShareholdingSegment, forms.ShareholdingForm, [
        ("Taxable acquisition gain (1TZ)", "taxable_acquisition_gain_1TZ"),
        ("Acquisition gain rebates (1UZ)", "acquisition_gain_rebates_1UZ"),
        ("Acquisition gain 50% rebates (1WZ)", "acquisition_gain_50p_rebates_1WZ"),
        ("Other taxable gain 1 (1TT)", "exercise_gain_1_1TT"),
        ("Other taxable gain 2 (1UT)", "exercise_gain_2_1UT"),
        ("Capital gain (3VG)", "capital_gain_3VG"),
        ("Capital loss (3VH) *NOT IMPLEMENTED*", "capital_loss_3VH"),
    ]),
]

@app.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>", methods=["GET"])
def taxstatement(project_id, taxstatement_id):
    project = models.Project.query.get(project_id)
    taxstatement = models.TaxStatement.query.get(taxstatement_id)

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
                tax_input[field] = value
        else:
            elt_object = None
        rendering_elements.append((elt.name, elt_object, elt_form, elt.fields, "upsert_"+elt.name.lower().replace(' ','')))
    tax_input["married"] = project.married
    tax_input["nb_children"] = project.nb_children
    tax_result, tax_flags = taxhelpers.simulate_tax(taxstatement.year, tax_input)
    net_taxes = tax_result["net_taxes"]
    print(net_taxes)
    return render_template("taxstatement.html",
                           project=project,
                           taxstatement=taxstatement,
                           statement_elements=rendering_elements,
                           tax_result=tax_result,
                           tax_flags=tax_flags)

def upsert_factory(element:StatementElement):
    elt_name = element.name.lower().replace(' ','')

    @app.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>/add_"+elt_name, endpoint="upsert_"+elt_name, methods=["POST"])
    def upsert_element(project_id, taxstatement_id):
        form = element.form()
        if form.validate_on_submit():
            taxstatement = models.TaxStatement.query.get(taxstatement_id)
            elt_id = getattr(taxstatement, elt_name + "_id")
            if elt_id:
                elt_object = element.model.query.get(elt_id)
                for _, field in element.fields:
                    setattr(elt_object, field, getattr(form, field).data)
                db.session.commit()
            else:
                elt_object = element.model()
                for _, field in element.fields:
                    setattr(elt_object, field, getattr(form, field).data)
                db.session.add(elt_object)
                db.session.commit()
                setattr(taxstatement, elt_name+"_id", elt_object.id)
                db.session.commit()
        return redirect(url_for("taxstatement", project_id=project_id, taxstatement_id=taxstatement_id))

    return upsert_element

upsert_functions = [upsert_factory(elt) for elt in statement_elements]
