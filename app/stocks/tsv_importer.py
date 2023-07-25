import csv
from io import TextIOWrapper
from datetime import datetime
from werkzeug.datastructures import FileStorage

from app.stocks.models import RSUPlan, RSUVesting, DirectStocks, StockOptions, StockOptionPlan, StockOptionVesting
from .. import db

def import_rsu_tsv(tsv_filename: FileStorage, project_id: int):
    # Python 3.11 required for the following (because https://docs.python.org/3.11/whatsnew/3.11.html#tempfile)
    rsuplan_reader = csv.DictReader(TextIOWrapper(tsv_filename.stream), dialect="excel", delimiter='\t')
    rsu_plans: dict[str, int] = {}
    for row in rsuplan_reader:
        plan_name = row["Plan name"]
        if plan_name in rsu_plans:
            plan_id = rsu_plans[plan_name]
        else:
            new_plan = RSUPlan(
                project_id=project_id,
                name=plan_name,
                taxpayer_owner=0,
                approval_date=datetime.strptime(row["Plan date"], "%d %b %Y").date(),
                symbol=row["Symbol"],
                stock_currency=row["Currency"]
            )
            db.session.add(new_plan)
            db.session.commit()
            plan_id = new_plan.id
            rsu_plans[plan_name] = plan_id
        vesting = RSUVesting(
            rsu_plan_id=plan_id,
            count=int(row["Count"]),
            vesting_date=datetime.strptime(row["Acquisition date"], "%d %b %Y").date(),
            acquisition_price=float(row["Acquisition price"])
        )
        db.session.add(vesting)
    db.session.commit()

def import_dstocks_tsv(tsv_filename: FileStorage, project_id: int):
    dstocks_reader = csv.DictReader(TextIOWrapper(tsv_filename.stream), dialect="excel", delimiter='\t')
    for row in dstocks_reader:
        new_dstock = DirectStocks(
            project_id=project_id,
            symbol=row["Symbol"],
            quantity=int(row["Count"]),
            acquisition_date=datetime.strptime(row["Acquisition date"], "%Y-%m-%d").date(),
            acquisition_price=float(row["Acquisition price"]),
            stock_currency=row["Currency"]
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
            db.session.add(new_plan)
            db.session.commit()
            plan_id = new_plan.id
            stockoptions_plans[plan_name] = plan_id

        vesting = StockOptionVesting(
            stockoption_plan_id=plan_id,
            count=int(row["Count"]),
            vesting_date=datetime.strptime(row["Acquisition date"], "%Y-%m-%d").date(),
        )
        db.session.add(vesting)
    db.session.commit()