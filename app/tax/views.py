from flask import render_template, redirect, url_for
import taxhelpers
from collections import namedtuple

from . import tax
from .forms import IncomeForm, CharityForm, RetirementInvestmentForm, ServicesChargesForm, FixedIncomeInvestmentForm, OtherInvestmentsForm, ShareholdingForm
from .models import *
from ..main.models import Project
from .. import db


@tax.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>/delete", methods=["GET", "POST"])
def taxstatement_delete(project_id, taxstatement_id):
    taxstatement = TaxStatement.query.get(taxstatement_id)
    db.session.delete(taxstatement)
    db.session.commit()
    return redirect(url_for("main.project_tax", project_id=project_id))

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

@tax.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>", methods=["GET"])
def taxstatement(project_id, taxstatement_id):
    project = Project.query.get(project_id)
    taxstatement = TaxStatement.query.get(taxstatement_id)

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

    @tax.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>/add_"+elt_name, endpoint="upsert_"+elt_name, methods=["POST"])
    def upsert_element(project_id, taxstatement_id):
        form = element.form()
        if form.validate_on_submit():
            taxstatement = TaxStatement.query.get(taxstatement_id)
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
        return redirect(url_for(".taxstatement", project_id=project_id, taxstatement_id=taxstatement_id))

    return upsert_element

upsert_functions = [upsert_factory(elt) for elt in statement_elements]