from app import db

class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), unique=True)
    married = db.Column(db.Boolean)
    nb_children = db.Column(db.Integer)

##### Stock-related tables #####

class DirectStocks(db.Model):
    __tablename__ = "direct_stocks"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    taxpayer_owner = db.Column(db.Integer) # 1 or 2, used for some tax return fields
    symbol = db.Column(db.String(16))
    quantity = db.Column(db.Integer)
    acquisition_date = db.Column(db.Date)
    acquisition_price = db.Column(db.Float)
    stock_currency = db.Column(db.String(3))

class RSUPlan(db.Model):
    __tablename__ = "rsu_plans"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    name = db.Column(db.String(256), unique=True)
    taxpayer_owner = db.Column(db.Integer)  # 1 or 2, used for some tax return fields
    grant_date = db.Column(db.Date)
    symbol = db.Column(db.String(16))
    stock_currency = db.Column(db.String(3))

class RSUVesting(db.Model):
    __tablename__ = "rsu_stocks"
    id = db.Column(db.Integer, primary_key=True)
    rsu_plan_id = db.Column(db.Integer, db.ForeignKey('rsu_plans.id'))
    count = db.Column(db.Integer)
    vesting_date = db.Column(db.Date)
    acquisition_price = db.Column(db.Float) # expressed in rsu_plans.stock_currency

class StockOptions(db.Model):
    __tablename__ = "stock_options"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    taxpayer_owner = db.Column(db.Integer)  # 1 or 2, used for some tax return fields
    grant_date = db.Column(db.Date)
    symbol = db.Column(db.String(16))
    stock_currency = db.Column(db.String(3))
    strike_price = db.Column(db.Float)
    strike_price_currency = db.Column(db.String(3))

class DirectStocksSale(db.Model):
    __tablename__ = "direct_stocks_sales"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    symbol = db.Column(db.String(16))
    quantity = db.Column(db.Integer)
    sell_date = db.Column(db.Date)
    sell_price = db.Column(db.Float)
    sell_currency = db.Column(db.String(3))
    fees = db.Column(db.Float) # in EUR


##### Tax-related tables #####

class TaxStatement(db.Model):
    __tablename__ = "tax_statements"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    year = db.Column(db.Integer)
    income_id = db.Column(db.Integer, db.ForeignKey('income_segments.id'))
    charity_id = db.Column(db.Integer, db.ForeignKey('charity_segments.id'))
    retirementinvestment_id = db.Column(db.Integer, db.ForeignKey('retirementinvestment_segments.id'))
    servicecharges_id = db.Column(db.Integer, db.ForeignKey('servicecharges_segments.id'))
    otherinvestments_id = db.Column(db.Integer, db.ForeignKey('otherinvestments_segments.id'))
    shareholding_id = db.Column(db.Integer, db.ForeignKey('shareholding_segments.id'))

class IncomeSegment(db.Model):
    __tablename__ = "income_segments"
    id = db.Column(db.Integer, primary_key=True)
    salary_1_1AJ = db.Column(db.Integer)
    salary_2_1BJ = db.Column(db.Integer)

class CharitySegment(db.Model):
    __tablename__ = "charity_segments"
    id = db.Column(db.Integer, primary_key=True)
    charity_donation_7UD = db.Column(db.Integer)
    charity_donation_7UF = db.Column(db.Integer)

class RetirementInvestmentSegment(db.Model):
    __tablename__ = "retirementinvestment_segments"
    id = db.Column(db.Integer, primary_key=True)
    per_transfers_1_6NS = db.Column(db.Integer)
    per_transfers_2_6NT = db.Column(db.Integer)

class ServicesChargesSegment(db.Model):
    __tablename__ = "servicecharges_segments"
    id = db.Column(db.Integer, primary_key=True)
    children_daycare_fees_7GA = db.Column(db.Integer)
    home_services_7DB = db.Column(db.Integer)

class OtherInvestmentsSegment(db.Model):
    __tablename__ = "otherinvestments_segments"
    id = db.Column(db.Integer, primary_key=True)
    pme_capital_subscription_7CF = db.Column(db.Integer)
    pme_capital_subscription_7CH = db.Column(db.Integer)

class ShareholdingSegment(db.Model):
    __tablename__ = "shareholding_segments"
    id = db.Column(db.Integer, primary_key=True)
    taxable_acquisition_gain_1TZ = db.Column(db.Integer)
    acquisition_gain_rebates_1UZ = db.Column(db.Integer)
    acquisition_gain_50p_rebates_1WZ = db.Column(db.Integer)
    exercise_gain_1_1TT = db.Column(db.Integer)
    exercise_gain_2_1UT = db.Column(db.Integer)
    capital_gain_3VG = db.Column(db.Integer)
    capital_loss_3VH = db.Column(db.Integer)


