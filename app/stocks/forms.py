from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, IntegerField, SelectField, SubmitField, DateField, DecimalField, HiddenField, \
    IntegerRangeField
from wtforms.validators import NumberRange

class DirectStocksForm(FlaskForm):
    tp_owner = IntegerField("Taxpayer owner (1 or 2)", validators=[NumberRange(min=1, max=2)])
    symbol = StringField("Stock symbol")
    quantity = IntegerField("Quantity")
    acquisition_date = DateField("Acquisition date")
    acquisition_price = DecimalField("Acquisition price")
    stock_currency = StringField("Stock currency")
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

class SaleForm(FlaskForm):
    symbol = StringField("Stock symbol")
    stock_type = SelectField("Stock type", choices=["RSU", "ESPP", "STOCKOPTIONS"])
    quantity = IntegerField("Quantity")
    quantity_2 = IntegerRangeField("Quantity")
    sell_date = DateField("Sell date")
    sell_price = DecimalField("Sell price")
    sell_currency = StringField("Sell price currency")
    submit = SubmitField("Confirm")
