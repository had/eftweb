from flask_wtf import FlaskForm
from wtforms import Field, StringField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired

import inspect

class ProjectForm(FlaskForm):
    name = StringField("Name your project", validators=[DataRequired()])
    situation = SelectField("Marital situation", choices=["Married", "Single"])
    nb_children = IntegerField("Number of minor children")
    submit = SubmitField("Add")

class TaxStatementForm(FlaskForm):
    year = IntegerField("Year")
    submit = SubmitField("Add")

class IncomeForm(FlaskForm):
    income_1 = IntegerField("Income 1 (1AJ)", default=0)
    income_2 = IntegerField("Income 2 (1BJ)", default=0)
    submit = SubmitField("Confirm")

class CharityForm(FlaskForm):
    charity_7UD = IntegerField("Charity towards people in distress (7UD)", default=0)
    charity_7UF = IntegerField("Other charity (7UF)", default=0)
    submit = SubmitField("Confirm")

class RetirementInvestmentForm(FlaskForm):
    per_transfers_1_6NS = IntegerField("Investment on PER 1 (6NS)", default=0)
    per_transfers_2_6NT = IntegerField("Investment on PER 2 (6NT)", default=0)
    submit = SubmitField("Confirm")

# introspect a form and returns tuples of field names and labels
def form_to_fields(form):
    fields = inspect.getmembers(form, lambda x: issubclass(getattr(x,"field_class", type(None)), Field))
    return [(f_name, f_class.name) for f_name, f_class in fields if f_name != "submit"]