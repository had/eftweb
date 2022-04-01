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

class ServicesChargesForm(FlaskForm):
    children_daycare_fees_7GA = IntegerField("Children care - 1st child (7GA)", default=0)
    home_services_7DB = IntegerField("Home services (7DB)", default=0)
    submit = SubmitField("Confirm")

class OtherInvestmentsForm(FlaskForm):
    pme_capital_subscription_7CH = IntegerField("PME investment (7CH)", default=0)
    submit = SubmitField("Confirm")

class ShareholdingForm(FlaskForm):
    taxable_acquisition_gain_1TZ = IntegerField("Taxable acquisition gain (1TZ)", default=0)
    acquisition_gain_rebates_1UZ = IntegerField("Acquisition gain rebates (1UZ)", default=0)
    acquisition_gain_50p_rebates_1WZ = IntegerField("Acquisition gain 50% rebates (1WZ)", default=0)
    exercise_gain_1_1TT = IntegerField("Other taxable gain 1 (1TT)", default=0)
    exercise_gain_2_1UT = IntegerField("Other taxable gain 2 (1UT)", default=0)
    capital_gain_3VG = IntegerField("Capital gain (3VG)", default=0)
    capital_loss_3VH = IntegerField("Capital loss (3VH)", default=0)
    submit = SubmitField("Confirm")

# introspect a form and returns tuples of field names and labels
def form_to_fields(form):
    fields = inspect.getmembers(form, lambda x: issubclass(getattr(x,"field_class", type(None)), Field))
    return [(f_name, f_class.name) for f_name, f_class in fields if f_name != "submit"]