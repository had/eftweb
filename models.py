from app import db

class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), unique=True)

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
    income_1 = db.Column(db.Integer)
    income_2 = db.Column(db.Integer)

class CharitySegment(db.Model):
    __tablename__ = "charity_segments"
    id = db.Column(db.Integer, primary_key=True)
    charity_7UD = db.Column(db.Integer)
    charity_7UF = db.Column(db.Integer)

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


