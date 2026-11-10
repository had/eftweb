"""Read-only workbook adapters. No database access or workbook evaluation."""

import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from types import SimpleNamespace
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook

from app.constants import JAVASCRIPT_MAX_SAFE_INTEGER

from .validation import (
    allocation_error,
    calendar_date,
    grant_number_value,
    grant_payload,
    positive_quantity,
    purchase_payload,
    sale_payload,
)
from .xlsx_export import EXPORT_FORMAT, PLANS_HEADERS, SALES_HEADERS

MAX_UPLOAD = 10 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
MAX_ROWS = 100_000
BROKER_HEADERS = (
    "Record Type",
    "Symbol",
    "Plan Type",
    "Quantity",
    "Date Acquired",
    "Date Sold",
    "Total Proceeds",
    "Proceeds Per Share",
    "Order Type",
    "Grant Date",
    "Purchase Date",
    "Grant Number",
    "Vest Date",
    "Order Number",
)


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def text_value(value, label, required=True):
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        if not required and value in (None, ""):
            return None
        raise ValueError(f"{label} must be nonempty text of at most 256 characters")
    return value


def identifier(value, label):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # Larger numeric identifiers may already have lost digits in Excel.
        if value != int(value) or abs(value) >= 10**15:
            raise ValueError(f"{label} must be stored as text to preserve its digits")
        value = str(int(value))
    return text_value(value, label).strip()


def whole(value, label):
    try:
        if isinstance(value, bool):
            raise ValueError()
        number = Decimal(str(value))
        if (
            not number.is_finite()
            or not 0 < number <= JAVASCRIPT_MAX_SAFE_INTEGER
            or number != number.to_integral_value()
        ):
            raise ValueError()
        return positive_quantity(int(number), label)
    except (ValueError, InvalidOperation, OverflowError):
        raise ValueError(f"{label} must be a positive safe whole-share quantity") from None


def import_date(value, label, broker=False):
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if broker and isinstance(value, str):
        try:
            return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
        except ValueError:
            raise ValueError(f"{label} must be a US MM/DD/YYYY date") from None
    return calendar_date(value, label).isoformat()


def table(sheet, header_row, required):
    headers = [cell.value for cell in next(sheet.iter_rows(min_row=header_row, max_row=header_row))]
    if any(headers.count(name) != 1 for name in required):
        raise ValueError(f"{sheet.title}: missing or duplicate required columns")
    indices = {name: headers.index(name) for name in required}
    for row_number, cells in enumerate(sheet.iter_rows(min_row=header_row + 1), header_row + 1):
        if row_number > MAX_ROWS + header_row:
            raise ValueError("Workbook exceeds the 100,000-row limit")
        values = {
            name: cells[index].value if index < len(cells) else None
            for name, index in indices.items()
        }
        if not any(value is not None for value in values.values()):
            continue
        # Only imported fields are inspected; ignored broker tax columns are not evaluated.
        ignored = values.get("Record Type") == "Summary" or values.get("Order Type") == "ESPP STC"
        if not ignored and any(
            index < len(cells) and cells[index].data_type == "f" for index in indices.values()
        ):
            raise ValueError(
                f"{sheet.title} row {row_number}: formulas are not supported in import fields"
            )
        yield row_number, values


def parse_workbook(content):
    if not content or len(content) > MAX_UPLOAD:
        raise ValueError("Choose an XLSX file no larger than 10 MiB")
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sum(entry.file_size for entry in archive.infolist()) > MAX_EXPANDED:
                raise ValueError("Expanded workbook exceeds 100 MiB")
            if "xl/workbook.xml" not in archive.namelist():
                raise ValueError("Choose a valid XLSX workbook")
        workbook = load_workbook(
            BytesIO(content), read_only=True, data_only=False, keep_links=False
        )
    except (BadZipFile, KeyError, OSError) as error:
        raise ValueError("Choose a valid, unencrypted XLSX workbook") from error
    try:
        if len(workbook.worksheets) > 10:
            raise ValueError("Workbook contains too many worksheets")
        if sum(sheet.max_row or 0 for sheet in workbook) > MAX_ROWS + 10:
            raise ValueError("Workbook exceeds the 100,000-row limit")
        if any((sheet.max_column or 0) > 256 for sheet in workbook):
            raise ValueError("Workbook contains too many columns")
        if "Plans & vestings" in workbook.sheetnames:
            return parse_native(workbook)
        candidates = [
            sheet
            for sheet in workbook
            if set(BROKER_HEADERS).issubset(
                {cell.value for cell in next(sheet.iter_rows(max_row=1))}
            )
        ]
        if len(candidates) != 1:
            raise ValueError(
                "Unrecognized workbook: choose an app export or E*TRADE expanded gains/losses file"
            )
        return parse_etrade(candidates[0])
    finally:
        workbook.close()


def parse_native(workbook):
    if set(workbook.sheetnames) != {"Plans & vestings", "Sales"}:
        raise ValueError("An app export must contain Plans & vestings and Sales")
    sheet = workbook["Plans & vestings"]
    cells = list(sheet.iter_rows(max_row=4, max_col=2))
    if any(cell.data_type == "f" for row in cells for cell in row):
        raise ValueError("Formulas are not supported in metadata")
    metadata = {row[0].value: row[1].value for row in cells}
    version = metadata.get("schema_version")
    if (
        metadata.get("export_format") != EXPORT_FORMAT
        or type(version) is not int
        or version not in (1, 2)
    ):
        raise ValueError("Unsupported app export format or schema version")
    result = {
        "format": "eftweb",
        "version": version,
        "name": text_value(metadata.get("stock_name"), "Stock name"),
        "symbol": text_value(metadata.get("stock_symbol"), "Ticker").upper(),
        "grants": [],
        "purchases": [],
        "sales": [],
        "ignored": [],
    }
    grants, purchases, lots, sales, numbers = {}, {}, {}, {}, set()
    for row_number, row in table(sheet, 6, PLANS_HEADERS if version == 2 else PLANS_HEADERS[:-1]):
        kind = row["record_type"]
        if kind == "stock_purchase":
            if any(
                row[name] is not None
                for name in (
                    "grant_key",
                    "grant_date",
                    "grant_quantity",
                    "vesting_start_date",
                    "schedule_type",
                    "customized",
                    "vesting_key",
                    "vesting_date",
                    "vesting_quantity",
                    "grant_number",
                )
                if name in row
            ):
                raise ValueError(f"Plans row {row_number}: purchase contains grant fields")
            key = text_value(row["purchase_key"], "Purchase key")
            if key in purchases or key in lots:
                raise ValueError(f"Duplicate purchase key {key}")
            purchase = purchase_payload(
                {
                    "purchase_date": import_date(row["purchase_date"], "Purchase date"),
                    "quantity": whole(row["purchase_quantity"], "Purchase quantity"),
                    "plan_name": text_value(row["plan_name"], "Plan name"),
                }
            )
            purchases[key] = {**purchase, "key": key, "rows": [row_number]}
            lots[key] = ("purchase_id", purchase["purchase_date"], purchase["quantity"])
        elif kind in ("rsu_vesting", "rsu_grant"):
            if any(
                row[name] is not None
                for name in ("purchase_key", "purchase_date", "purchase_quantity")
            ):
                raise ValueError(f"Plans row {row_number}: grant contains purchase fields")
            key = text_value(row["grant_key"], "Grant key")
            if type(row["customized"]) is not bool:
                raise ValueError("Customized must be an Excel boolean")
            details = {
                "title": text_value(row["plan_name"], "Grant title"),
                "grant_number": grant_number_value(row.get("grant_number")),
                "grant_date": import_date(row["grant_date"], "Grant date"),
                "quantity": whole(row["grant_quantity"], "Grant quantity"),
                "vesting_start_date": import_date(row["vesting_start_date"], "Vesting start date"),
                "schedule_type": row["schedule_type"],
                "customized": row["customized"],
            }
            if key in grants:
                if grants[key]["details"] != details or kind == "rsu_grant" or grants[key]["empty"]:
                    raise ValueError(f"Inconsistent repeated grant {key}")
            else:
                if details["grant_number"] and details["grant_number"] in numbers:
                    raise ValueError("Duplicate grant number in workbook")
                numbers.add(details["grant_number"])
                grants[key] = {
                    "key": key,
                    "details": details,
                    "vestings": [],
                    "empty": kind == "rsu_grant",
                    "rows": [],
                }
            grants[key]["rows"].append(row_number)
            if kind == "rsu_vesting":
                vesting_key = text_value(row["vesting_key"], "Vesting key")
                if vesting_key in lots:
                    raise ValueError(f"Duplicate acquisition key {vesting_key}")
                vesting = {
                    "key": vesting_key,
                    "date": import_date(row["vesting_date"], "Vesting date"),
                    "quantity": whole(row["vesting_quantity"], "Vesting quantity"),
                }
                grants[key]["vestings"].append(vesting)
                lots[vesting_key] = ("vesting_id", vesting["date"], vesting["quantity"])
            elif any(
                row[name] is not None
                for name in ("vesting_key", "vesting_date", "vesting_quantity")
            ):
                raise ValueError("Grant-only row contains vesting fields")
        else:
            raise ValueError(f"Plans row {row_number}: unsupported record type")
    for grant in grants.values():
        normalized = grant_payload(
            {**grant["details"], "vestings": grant["vestings"]},
            SimpleNamespace(symbol=result["symbol"]),
            allow_empty=True,
        )
        result["grants"].append(
            {
                **normalized,
                "key": grant["key"],
                "vestings": grant["vestings"],
                "rows": grant["rows"],
            }
        )
    result["purchases"] = list(purchases.values())
    allocation_keys = defaultdict(set)
    for row_number, row in table(
        workbook["Sales"], 1, SALES_HEADERS if version == 2 else SALES_HEADERS[:-3]
    ):
        key = text_value(row["sale_key"], "Sale key")
        details = {
            "transaction_date": import_date(row["transaction_date"], "Sale date"),
            "quantity": whole(row["sale_quantity"], "Sale quantity"),
            "proceeds_per_share": str(row["proceeds_per_share"]),
            "currency": row["currency"],
            **{name: row.get(name) for name in SALES_HEADERS[-3:]},
        }
        provenance = [details[name] for name in SALES_HEADERS[-3:]]
        if any(value is not None for value in provenance):
            if (
                details["import_source"] != "etrade"
                or not isinstance(details["source_fingerprint"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", details["source_fingerprint"])
            ):
                raise ValueError("Invalid broker provenance")
            text_value(details["source_order_number"], "Broker order number")
        if key in sales and sales[key]["details"] != details:
            raise ValueError(f"Inconsistent repeated sale {key}")
        sale = sales.setdefault(
            key, {"key": key, "details": details, "allocations": [], "rows": []}
        )
        sale["rows"].append(row_number)
        sources = [row[name] for name in ("vesting_key", "purchase_key") if row[name] is not None]
        if not sources and row["allocation_quantity"] is None:
            if len(sale["rows"]) != 1:
                raise ValueError("A sale-only row cannot be repeated")
            sale["empty"] = True
            continue
        if len(sources) != 1 or sale.get("empty"):
            raise ValueError("Each sale allocation must identify one acquisition")
        source = sources[0]
        expected_type = "vesting_id" if row["vesting_key"] is not None else "purchase_id"
        if source not in lots or lots[source][0] != expected_type:
            raise ValueError(f"Sale {key}: broken acquisition reference {source}")
        if source in allocation_keys[key]:
            raise ValueError(f"Sale {key}: duplicate allocation")
        allocation_keys[key].add(source)
        sale["allocations"].append(
            {
                "source_key": source,
                "quantity": whole(row["allocation_quantity"], "Allocation quantity"),
            }
        )
    used = defaultdict(int)
    lot_ids = {key: index for index, key in enumerate(lots, 1)}
    pockets = {
        (kind, lot_ids[key]): (date.fromisoformat(acquired), quantity)
        for key, (kind, acquired, quantity) in lots.items()
    }
    for sale in sales.values():
        # Temporary numeric lot IDs let the same domain validator check native data.
        allocations = [
            {lots[row["source_key"]][0]: lot_ids[row["source_key"]], "quantity": row["quantity"]}
            for row in sale["allocations"]
        ]
        normalized = sale_payload({**sale["details"], "allocations": allocations}, allow_empty=True)
        error = allocation_error(normalized, pockets, used)
        if error:
            raise ValueError(f"Sale {sale['key']}: {error[0]}")
        for allocation in normalized["allocations"]:
            source = "vesting_id" if "vesting_id" in allocation else "purchase_id"
            used[(source, allocation[source])] += allocation["quantity"]
        result["sales"].append(
            {
                **sale["details"],
                **normalized,
                "allocations": sale["allocations"],
                "key": sale["key"],
                "rows": sale["rows"],
            }
        )
    return result


def parse_etrade(sheet):
    result = {
        "format": "etrade",
        "symbol": None,
        "grants": [],
        "purchases": [],
        "sales": [],
        "ignored": [],
    }
    groups = {}
    symbols = set()
    for row_number, row in table(sheet, 1, BROKER_HEADERS):
        if row["Record Type"] == "Summary":
            result["ignored"].append({"row": row_number, "reason": "Summary"})
            continue
        symbol = str(row["Symbol"] or "").strip().upper()
        if symbol:
            symbols.add(symbol)
        if row["Order Type"] == "ESPP STC":
            result["ignored"].append({"row": row_number, "reason": "ESPP STC (sell to cover)"})
            continue
        try:
            if row["Record Type"] != "Sell" or (row["Plan Type"], row["Order Type"]) not in (
                ("RS", "Sell Restricted Stock"),
                ("ESPP", "Sell ESPP"),
            ):
                raise ValueError("Unsupported record, plan, or order type")
            if not symbol:
                raise ValueError("Ticker is required")
            quantity = whole(row["Quantity"], "Quantity")
            sale = sale_payload(
                {
                    "transaction_date": import_date(row["Date Sold"], "Date Sold", broker=True),
                    "quantity": quantity,
                    "proceeds_per_share": row["Proceeds Per Share"],
                    "allocations": [{"vesting_id": 1, "quantity": quantity}],
                }
            )
            order = identifier(row["Order Number"], "Order Number")
            source = {
                "plan_type": row["Plan Type"],
                "acquired_date": import_date(row["Date Acquired"], "Date Acquired", broker=True),
                "grant_date": import_date(row["Grant Date"], "Grant Date", broker=True),
            }
            if row["Plan Type"] == "RS":
                source.update(
                    grant_number=identifier(row["Grant Number"], "Grant Number"),
                    date=import_date(row["Vest Date"], "Vest Date", broker=True),
                )
            else:
                source["date"] = import_date(row["Purchase Date"], "Purchase Date", broker=True)
            identity = (order, sale["transaction_date"], sale["proceeds_per_share"], "USD")
            group = groups.setdefault(
                identity,
                {
                    **sale,
                    "quantity": 0,
                    "allocations": [],
                    "rows": [],
                    "warnings": [],
                    "sources": {},
                    "import_source": "etrade",
                    "source_order_number": order,
                    "key": fingerprint(identity),
                    "errors": [],
                },
            )
            group["quantity"] += quantity
            group["rows"].append(row_number)
            source_key = fingerprint(source)
            lot = group["sources"].setdefault(source_key, {**source, "quantity": 0, "rows": []})
            lot["quantity"] += quantity
            lot["rows"].append(row_number)
            try:
                proceeds = Decimal(str(row["Total Proceeds"]))
                if not proceeds.is_finite():
                    raise InvalidOperation()
                if abs(proceeds - Decimal(sale["proceeds_per_share"]) * quantity) > Decimal("0.01"):
                    group["warnings"].append(
                        f"Row {row_number}: Total Proceeds differs from quantity × price"
                    )
            except InvalidOperation:
                group["warnings"].append(
                    f"Row {row_number}: Total Proceeds is unavailable for cross-checking"
                )
        except (ValueError, TypeError) as error:
            result["sales"].append(
                {
                    "key": f"row:{row_number}",
                    "rows": [row_number],
                    "errors": [str(error)],
                    "warnings": [],
                    "quantity": None,
                    "transaction_date": None,
                    "proceeds_per_share": None,
                    "sources": [],
                    "allocations": [],
                }
            )
    if len(symbols) > 1:
        raise ValueError("Mixed-symbol files are not supported; filter to the current stock first")
    result["symbol"] = next(iter(symbols), None)
    for group in groups.values():
        group["sources"] = sorted(
            group["sources"].values(),
            key=lambda source: fingerprint({k: v for k, v in source.items() if k != "rows"}),
        )
        facts = {
            key: group[key]
            for key in (
                "source_order_number",
                "transaction_date",
                "proceeds_per_share",
                "currency",
                "quantity",
            )
        }
        facts["sources"] = [
            {key: value for key, value in source.items() if key != "rows"}
            for source in group["sources"]
        ]
        group["source_fingerprint"] = fingerprint(facts)
        result["sales"].append(group)
    result["sales"].sort(key=lambda sale: (sale["transaction_date"] or "", sale["key"]))
    return result
