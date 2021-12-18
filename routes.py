from flask import render_template, redirect, session, url_for, flash
import forms
import models
import taxsim
from app import app, db


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

@app.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>", methods=["GET"])
def taxstatement(project_id, taxstatement_id):
    project = models.Project.query.get(project_id)
    taxstatement = models.TaxStatement.query.get(taxstatement_id)

    income_form = forms.IncomeForm()
    if taxstatement.income_id:
        income_object = models.IncomeSegment.query.get(taxstatement.income_id)
        income_form.income_1.data = income_object.income_1
        income_form.income_2.data = income_object.income_2
    else:
        income_object = None

    charity_form = forms.CharityForm()
    if taxstatement.charity_id:
        charity_object = models.CharitySegment.query.get(taxstatement.charity_id)
        charity_form.charity_7UD.data = charity_object.charity_7UD
        charity_form.charity_7UF.data = charity_object.charity_7UF
    else:
        charity_object = None

    net_taxes = taxsim.simulateTax(income_object, charity_object)
    return render_template("taxstatement.html",
                           project=project,
                           taxstatement=taxstatement,
                           income=income_object,
                           income_form=income_form,
                           charity=charity_object,
                           charity_form=charity_form,
                           tax_result=net_taxes
    )

@app.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>/add_income", methods=["POST"])
def upsert_income(project_id, taxstatement_id):
    form = forms.IncomeForm()
    if form.validate_on_submit():
        taxstatement = models.TaxStatement.query.get(taxstatement_id)
        if taxstatement.income_id:
            income = models.IncomeSegment.query.get(taxstatement.income_id)
            income.income_1 = form.income_1.data
            income.income_2 = form.income_2.data
            db.session.commit()
        else:
            income = models.IncomeSegment(income_1=form.income_1.data, income_2=form.income_2.data)
            db.session.add(income)
            db.session.commit()
            taxstatement.income_id = income.id
            db.session.commit()
    return redirect(url_for("taxstatement", project_id=project_id, taxstatement_id=taxstatement_id))

@app.route("/project/<int:project_id>/taxstatement/<int:taxstatement_id>/add_charity", methods=["POST"])
def upsert_charity(project_id, taxstatement_id):
    form = forms.CharityForm()
    if form.validate_on_submit():
        taxstatement = models.TaxStatement.query.get(taxstatement_id)
        if taxstatement.charity_id:
            charity = models.CharitySegment.query.get(taxstatement.charity_id)
            charity.charity_7UD = form.charity_7UD.data
            charity.charity_7UF = form.charity_7UF.data
            db.session.commit()
        else:
            charity = models.CharitySegment(charity_7UD=form.charity_7UD.data, charity_7UF=form.charity_7UF.data)
            db.session.add(charity)
            db.session.commit()
            taxstatement.charity_id = charity.id
            db.session.commit()
    return redirect(url_for("taxstatement", project_id=project_id, taxstatement_id=taxstatement_id))