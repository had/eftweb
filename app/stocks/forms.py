from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import StringField, IntegerField, SelectField, SubmitField, DateField, DecimalField, HiddenField
from wtforms.validators import NumberRange

class DirectStocksForm(FlaskForm):
    tp_owner = IntegerField("Taxpayer owner (1 or 2)", validators=[NumberRange(min=1, max=2)])
    symbol = StringField("Stock symbol")
    quantity = IntegerField("Quantity")
    acquisition_date = DateField("Acquisition date")
    acquisition_price = DecimalField("Acquisition price")
    stock_currency = StringField("Stock currency")
    submit = SubmitField("Confirm")

class RsuPlanForm(FlaskForm):
    name = StringField("Name")
    tp_owner = IntegerField("Taxpayer owner (1 or 2)", validators=[NumberRange(min=1, max=2)])
    approval_date = DateField("Approval date")
    symbol = StringField("Stock symbol")
    stock_currency = StringField("Stock currency")
    # tsv_file = FileField("Vesting data (optional)")
    submit = SubmitField("Confirm")

class RsuImportForm(FlaskForm):
    tsv_file = FileField("RSU data")
    submit = SubmitField("Confirm")

class DirectStocksImportForm(FlaskForm):
    tsv_file = FileField("Direct Stocks data")
    submit = SubmitField("Confirm")

class StockOptionsImportForm(FlaskForm):
    tsv_file = FileField("Stock Options data")
    tp_owner = IntegerField("Taxpayer owner (1 or 2)", validators=[NumberRange(min=1, max=2)])
    submit = SubmitField("Confirm")

class RsuVestingForm(FlaskForm):
    rsuplan_id = HiddenField("rsuplanId")
    periodicity = SelectField("Periodicity", choices=["No", "Monthly", "Quarterly"])
    quantity = IntegerField("Quantity")
    vesting_date = DateField("Vesting date")
    number_of_periods = IntegerField("Number of periods")
    acquisition_price = DecimalField("Acquisition price")
    submit = SubmitField("Confirm")

class DirectStocksSaleForm(FlaskForm):
    symbol = StringField("Stock symbol")
    quantity = IntegerField("Quantity")
    sell_date = DateField("Sell date")
    sell_price = DecimalField("Sell price")
    sell_currency = StringField("Sell price currency")
    fees = DecimalField("Fees (in same currency)")
    submit = SubmitField("Confirm")

class RsuSaleForm(FlaskForm):
    symbol = StringField("Stock symbol")
    quantity = IntegerField("Quantity")
    sell_date = DateField("Sell date")
    sell_price = DecimalField("Sell price")
    sell_currency = StringField("Sell price currency")
    fees = DecimalField("Fees (in same currency)")
    submit = SubmitField("Confirm")
