from easyfrenchtax import StockType

from .. import db


class DirectStocks(db.Model):
    __tablename__ = "direct_stocks"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
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


class StockOptionPlan(db.Model):
    __tablename__ = "stockoption_plans"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    name = db.Column(db.String(256), unique=True)
    taxpayer_owner = db.Column(db.Integer)  # 1 or 2, used for some tax return fields
    symbol = db.Column(db.String(16))
    stock_currency = db.Column(db.String(3))
    strike_price = db.Column(db.Float)


class StockOptionVesting(db.Model):
    __tablename__ = "stockoption_vestings"
    id = db.Column(db.Integer, primary_key=True)
    stockoption_plan_id = db.Column(db.Integer, db.ForeignKey('stockoption_plans.id'))
    count = db.Column(db.Integer)
    vesting_date = db.Column(db.Date)


class SaleEvent(db.Model):
    __tablename__ = "sale_events"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    type = db.Column(db.Enum(StockType))
    symbol = db.Column(db.String(16))
    quantity = db.Column(db.Integer)
    sell_date = db.Column(db.Date)
    sell_price = db.Column(db.Float)
    sell_currency = db.Column(db.String(3))
    fees = db.Column(db.Float)  # in sell_currency

# TODO cleanup
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

# TODO cleanup
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
