from flask import render_template, redirect, session, url_for, flash
import forms
import models
import taxsim
from app import app, db
from collections import namedtuple

@app.route("/", methods=["GET", "POST"])
def index():
    form = forms.ProjectForm()
    if form.validate_on_submit():
        project = models.Project(name=form.name.data)
        db.session.add(project)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        flash(f"Project added (total {len(models.Project.query.all())} projects)")
        return redirect(url_for('project', project_id=project.id))
    projects = models.Project.query.all()
    return render_template("index.html", name="Guest", projects=projects, form=form)

@app.route("/project/<int:project_id>", methods=["GET", "POST"])
def project(project_id):
    project = models.Project.query.get(project_id)
    form = forms.TaxStatementForm()
    if form.validate_on_submit():
        taxstatement = models.TaxStatement(project_id=project_id, year=form.year.data)
        db.session.add(taxstatement)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        flash(f"Tax statement added")
        return redirect(url_for('project', project_id=project.id))
    else:
        # prefill with current year-1
        form.year.data = 2020
    statements = models.TaxStatement.query.filter_by(project_id=project.id).all()
    return render_template("project.html", project=project, form=form, taxstatements=statements)


@app.route("/project/<int:project_id>/delete", methods=["GET", "POST"])
def project_delete(project_id):
    project = models.Project.query.get(project_id)
    db.session.delete(project)
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>/delete", methods=["GET", "POST"])
def taxstatement_delete(project_id, taxstatement_id):
    taxstatement = models.TaxStatement.query.get(taxstatement_id)
    db.session.delete(taxstatement)
    db.session.commit()
    return redirect(url_for("project", project_id=project_id))

StatementElement = namedtuple("StatementElement", ["name", "model", "form", "fields", "upsert_route"])
statement_elements = [
   StatementElement("Income", models.IncomeSegment, forms.IncomeForm, [
       ("Income person 1", "income_1"),
       ("Income person 2", "income_2")
   ], "upsert_income"),
   StatementElement("Charity", models.CharitySegment, forms.CharityForm, [
       ("Charity towards people in distress (7UD)", "charity_7UD"),
       ("Other charity (7UF)", "charity_7UF")
   ], "upsert_charity"),
]

@app.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>", methods=["GET"])
def taxstatement(project_id, taxstatement_id):
    project = models.Project.query.get(project_id)
    taxstatement = models.TaxStatement.query.get(taxstatement_id)

    rendering_elements = []
    for elt in statement_elements:
        elt_form = elt.form()
        elt_id = getattr(taxstatement, elt.name.lower()+"_id")
        if elt_id:
            elt_object = elt.model.query.get(elt_id)
            for _, field in elt.fields:
                getattr(elt_form, field).data = getattr(elt_object, field)
        else:
            elt_object = None
        # upsert_fn = upsert_factory(elt)
        rendering_elements.append((elt.name, elt_object, elt_form, elt.fields, "upsert_"+elt.name.lower()))

    net_taxes = taxsim.simulateTax({elt[0]: elt[1] for elt in rendering_elements})
    return render_template("taxstatement.html",
                           project=project,
                           taxstatement=taxstatement,
                           statement_elements=rendering_elements,
                           tax_result=net_taxes)

def upsert_factory(element:StatementElement):
    elt_name = element.name.lower()

    @app.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>/add_"+elt_name, endpoint="upsert_"+elt_name, methods=["POST"])
    def upsert_element(project_id, taxstatement_id):
        form = element.form()
        if form.validate_on_submit():
            taxstatement = models.TaxStatement.query.get(taxstatement_id)
            if getattr(taxstatement, elt_name+"_id"):
                elt_object = element.model.query.get(taxstatement.income_id)
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
