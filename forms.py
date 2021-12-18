from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired


class ProjectForm(FlaskForm):
    name = StringField("Name your project", validators=[DataRequired()])
    situation = SelectField("Marital situation", choices=["Married", "Single"])
    nb_children = IntegerField("Number of minor children")
    submit = SubmitField("Add")

class TaxStatementForm(FlaskForm):
    year = IntegerField("Year")
    submit = SubmitField("Add")

class IncomeForm(FlaskForm):
    income_1 = IntegerField("Income 1 (1AJ)")
    income_2 = IntegerField("Income 2 (1BJ)")
    submit = SubmitField("Confirm")

class CharityForm(FlaskForm):
    charity_7UD = IntegerField("Charity towards people in distress (7UD)")
    charity_7UF = IntegerField("Other charity (7UF)")
    submit = SubmitField("Confirm")
