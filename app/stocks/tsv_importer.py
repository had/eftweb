import csv
from io import TextIOWrapper
from datetime import datetime, date

from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import FileStorage

from app.stocks.models import RSUPlan, RSUVesting, DirectStocks, DirectStocksPlan, StockOptionPlan, StockOptionVesting
from app.stocks.ticker import ticker
from .. import db

def import_rsu_tsv(tsv_filename: FileStorage, project_id: int):
    today = date.today()
    # Python 3.11 required for the following (because https://docs.python.org/3.11/whatsnew/3.11.html#tempfile)
    rsuplan_reader = csv.DictReader(TextIOWrapper(tsv_filename.stream), dialect="excel", delimiter='\t')
    rsu_plans: dict[str, int] = {}
    for row in rsuplan_reader:
        print(row)
        symbol = row["Symbol"]
        plan_name = row["Plan name"]
        if plan_name in rsu_plans:
            plan_id = rsu_plans[plan_name]
        else:
            new_plan = RSUPlan(
                project_id=project_id,
                name=plan_name,
                approval_date=datetime.strptime(row["Plan date"], "%Y-%m-%d").date(),
                symbol=symbol,
                stock_currency=row["Currency"]
            )
            try:
                db.session.add(new_plan)
                db.session.commit()
                plan_id = new_plan.id
                rsu_plans[plan_name] = plan_id
            except IntegrityError as e:
                print(e)
                db.session.rollback()
                return

        vesting_date = datetime.strptime(row["Acquisition date"], "%Y-%m-%d").date()
        acquisition_price = float(row["Acquisition price"])
        if vesting_date < today and acquisition_price == 0:
            acquisition_price = ticker.get_stock_closing_history(symbol)[vesting_date]
        vesting = RSUVesting(
            rsu_plan_id=plan_id,
            count=int(row["Count"]),
            vesting_date=vesting_date,
            acquisition_price=acquisition_price
        )
        db.session.add(vesting)
    db.session.commit()

def import_dstocks_tsv(tsv_filename: FileStorage, project_id: int):
    dstocks_reader = csv.DictReader(TextIOWrapper(tsv_filename.stream), dialect="excel", delimiter='\t')
    dstocks_plans: dict[str, int] = {}
    for row in dstocks_reader:
        symbol = row["Symbol"]
        plan_name = row["Plan name"]
        if plan_name in dstocks_plans:
            plan_id = dstocks_plans[plan_name]
        else:
            new_plan = DirectStocksPlan(
                project_id=project_id,
                name=plan_name,
                symbol=symbol,
                stock_currency=row["Currency"]
            )
            try:
                db.session.add(new_plan)
                db.session.commit()
                plan_id = new_plan.id
                dstocks_plans[plan_name] = plan_id
            except IntegrityError:
                db.session.rollback()
                return

        new_dstock = DirectStocks(
            direct_stocks_plan_id=plan_id,
            quantity=int(row["Count"]),
            acquisition_date=datetime.strptime(row["Acquisition date"], "%Y-%m-%d").date(),
            acquisition_price=float(row["Acquisition price"])
        )
        db.session.add(new_dstock)
    db.session.commit()

def import_stockoptions_tsv(tsv_filename: FileStorage, owner: int, project_id: int):
    stockoptions_reader = csv.DictReader(TextIOWrapper(tsv_filename.stream), dialect="excel", delimiter='\t')
    stockoptions_plans: dict[str, int] = {}
    for row in stockoptions_reader:
        plan_name = row["Plan name"]
        if plan_name in stockoptions_plans:
            plan_id = stockoptions_plans[plan_name]
        else:
            new_plan = StockOptionPlan(
                project_id=project_id,
                name=plan_name,
                taxpayer_owner=owner,
                symbol=row["Symbol"],
                stock_currency=row["Currency"],
                strike_price=row["Strike price"]
            )
            try:
                db.session.add(new_plan)
                db.session.commit()
                plan_id = new_plan.id
                stockoptions_plans[plan_name] = plan_id
            except IntegrityError:
                db.session.rollback()
                return

        vesting = StockOptionVesting(
            stockoption_plan_id=plan_id,
            count=int(row["Count"]),
            vesting_date=datetime.strptime(row["Acquisition date"], "%Y-%m-%d").date(),
        )
        print(vesting)
        db.session.add(vesting)
    db.session.commit()