from .. import db


class DirectStocks(db.Model):
    __tablename__ = "direct_stocks"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    taxpayer_owner = db.Column(db.Integer)  # 1 or 2, used for some tax return fields
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
    approval_date = db.Column(db.Date)
    symbol = db.Column(db.String(16))
    stock_currency = db.Column(db.String(3))


class RSUVesting(db.Model):
    __tablename__ = "rsu_stocks"
    id = db.Column(db.Integer, primary_key=True)
    rsu_plan_id = db.Column(db.Integer, db.ForeignKey('rsu_plans.id'))
    count = db.Column(db.Integer)
    vesting_date = db.Column(db.Date)
    acquisition_price = db.Column(db.Float)  # expressed in rsu_plans.stock_currency


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
    fees = db.Column(db.Float)  # in sell_currency


class RSUSale(db.Model):
    __tablename__ = "rsu_sales"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    symbol = db.Column(db.String(16))
    quantity = db.Column(db.Integer)
    sell_date = db.Column(db.Date)
    sell_price = db.Column(db.Float)
    sell_currency = db.Column(db.String(3))
    fees = db.Column(db.Float)  # in sell_currency