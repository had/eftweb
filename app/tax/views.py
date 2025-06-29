from flask import render_template, redirect, url_for
from taxhelpers import StatementElement, statement_elements, prepare_tax_input, simulate_tax
from easyfrenchtax import TaxField

from . import tax
from .models import *
from ..main.models import Project
from .. import db


@tax.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>/delete", methods=["GET", "POST"])
def taxstatement_delete(project_id, taxstatement_id):
    taxstatement = TaxStatement.query.get(taxstatement_id)
    db.session.delete(taxstatement)
    db.session.commit()
    return redirect(url_for("main.project_tax", project_id=project_id))



@tax.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>", methods=["GET"])
def taxstatement(project_id, taxstatement_id):
    project = Project.query.get(project_id)
    taxstatement = TaxStatement.query.get(taxstatement_id)

    tax_input, rendering_elements = prepare_tax_input(project, taxstatement)
    tax_result, tax_flags = simulate_tax(taxstatement.year, tax_input)
    total_taxes = tax_result[TaxField.NET_TAXES] + tax_result[TaxField.NET_SOCIAL_TAXES]

    return render_template("taxstatement.html",
                           project=project,
                           taxstatement=taxstatement,
                           statement_elements=rendering_elements,
                           total_taxes=total_taxes,
                           tax_result=tax_result,
                           tax_flags=tax_flags)

def upsert_factory(element: StatementElement):
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