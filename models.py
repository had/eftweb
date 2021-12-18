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

