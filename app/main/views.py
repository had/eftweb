import datetime

from flask import render_template, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError

from . import main
from .forms import ProjectForm, TaxStatementForm
from .. import db
from .. import models


@main.route("/", methods=["GET", "POST"])
def index():
    form = ProjectForm()
    if form.validate_on_submit():
        project = models.Project(
            name=form.name.data
        )
        db.session.add(project)
        try:
            db.session.commit()
            flash(f"Project added (total {len(models.Project.query.all())} projects)")
            return redirect(url_for('.project_tax', project_id=project.id))
        except IntegrityError:
            db.session.rollback()
    projects = models.Project.query.all()
    return render_template("index.html", name="Guest", projects=projects, form=form)


@main.route("/project/<int:project_id>", methods=["GET", "POST"])
def project_tax(project_id):
    project = models.Project.query.get(project_id)
    # prepare project form in case of edit/update
    project_form = ProjectForm()
    project_form.name.data = project.name
    project_form.situation.data = "Married" if project.married else "Single"
    project_form.nb_children.data = project.nb_children
    # tax form
    tax_form = TaxStatementForm()
    if tax_form.validate_on_submit():
        tax_statement = models.TaxStatement(project_id=project_id, year=tax_form.year.data)
        db.session.add(tax_statement)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        flash(f"Tax statement added")
        return redirect(url_for('.project_tax', project_id=project.id))
    else:
        # prefill with current year
        tax_form.year.data = datetime.date.today().year
    statements = models.TaxStatement.query.filter_by(project_id=project.id).all()
    return render_template("project_tax.html", project=project, tax_form=tax_form, project_edit_from=project_form,
                           taxstatements=statements)


@main.route("/project/<int:project_id>/edit", methods=["POST"])
def project_update(project_id):
    form = ProjectForm()
    if form.validate_on_submit():
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
    return redirect(url_for('.project_tax', project_id=project_id))


@main.route("/project/<int:project_id>/delete", methods=["GET", "POST"])
def project_delete(project_id):
    project = models.Project.query.get(project_id)
    db.session.delete(project)
    db.session.commit()
    return redirect(url_for(".index"))
