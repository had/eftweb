from flask_wtf import FlaskForm
from wtforms import IntegerField, SubmitField

class IncomeForm(FlaskForm):
    salary_1_1AJ = IntegerField("Income 1 (1AJ)", default=0)
    salary_2_1BJ = IntegerField("Income 2 (1BJ)", default=0)
    submit = SubmitField("Confirm")

class CharityForm(FlaskForm):
    charity_donation_7UD = IntegerField("Charity donation for people in distress (7UD)", default=0)
    charity_donation_7UF = IntegerField("Other charity donations (7UF)", default=0)
    submit = SubmitField("Confirm")

class RetirementInvestmentForm(FlaskForm):
    per_transfers_1_6NS = IntegerField("Investment on PER 1 (6NS)", default=0)
    per_transfers_2_6NT = IntegerField("Investment on PER 2 (6NT)", default=0)
    submit = SubmitField("Confirm")

class ServicesChargesForm(FlaskForm):
    children_daycare_fees_7GA = IntegerField("Children care - 1st child (7GA)", default=0)
    home_services_7DB = IntegerField("Home services (7DB)", default=0)
    submit = SubmitField("Confirm")

class FixedIncomeInvestmentForm(FlaskForm):
    fixed_income_interests_2TR = IntegerField("Fixed income investments (2TR)", default=0)
    fixed_income_interests_already_taxed_2BH = IntegerField("Fixed income already taxed (2BH)", default=0)
    interest_tax_already_paid_2CK = IntegerField("Tax already paid on fixed income (2CK)", default=0)
    submit = SubmitField("Confirm")

class OtherInvestmentsForm(FlaskForm):
    pme_capital_subscription_7CF = IntegerField("PME investment 1st period (7CF)", default=0)
    pme_capital_subscription_7CH = IntegerField("PME investment 2nd period (7CH)", default=0)
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