from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired


class ProjectForm(FlaskForm):
    name = StringField("Name your project", validators=[DataRequired()])
    situation = SelectField("Marital situation", choices=["Married", "Single"])
    nb_children = IntegerField("Number of minor children")
    submit = SubmitField("Submit")

class TaxStatementForm(FlaskForm):
    year = IntegerField("Year")
    submit = SubmitField("Add")
