"""Versioned, lossless interchange format for the current stock model."""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

EXPORT_FORMAT = "eftweb.stock"
SCHEMA_VERSION = 1
PLANS_HEADERS = (
    "record_type",
    "grant_key",
    "plan_name",
    "grant_date",
    "grant_quantity",
    "vesting_start_date",
    "schedule_type",
    "customized",
    "vesting_key",
    "vesting_date",
    "vesting_quantity",
    "purchase_key",
    "purchase_date",
    "purchase_quantity",
)
SALES_HEADERS = (
    "sale_key",
    "transaction_date",
    "sale_quantity",
    "proceeds_per_share",
    "currency",
    "vesting_key",
    "purchase_key",
    "allocation_quantity",
)


def append_values(sheet, values):
    """Keep literal strings and integers that Excel would otherwise round."""
    sheet.append(
        [
            (
                str(value)
                if isinstance(value, int) and not isinstance(value, bool) and abs(value) >= 10**15
                else value
            )
            for value in values
        ]
    )
    for cell in sheet[sheet.max_row]:
        if isinstance(cell.value, str):
            cell.data_type = "s"
            cell.number_format = "@"


def format_table(sheet, headers, header_row):
    sheet.freeze_panes = f"A{header_row + 1}"
    sheet.auto_filter.ref = f"A{header_row}:{get_column_letter(len(headers))}{sheet.max_row}"
    sheet.row_dimensions[header_row].height = 32
    for column, header in enumerate(headers, start=1):
        cell = sheet.cell(header_row, column)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="244B63")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        width = max(18, len(header) + 2)
        if header == "plan_name":
            width = 40
        sheet.column_dimensions[get_column_letter(column)].width = width


def build_stock_export(stock):
    """Return an XLSX stream from a fully materialized stock snapshot."""
    workbook = Workbook()
    plans = workbook.active
    plans.title = "Plans & vestings"
    for label, value in (
        ("export_format", EXPORT_FORMAT),
        ("schema_version", SCHEMA_VERSION),
        ("stock_name", stock["name"]),
        ("stock_symbol", stock["symbol"]),
    ):
        append_values(plans, (label, value))
        plans.cell(plans.max_row, 1).font = Font(bold=True)
    append_values(plans, (None,))
    append_values(plans, PLANS_HEADERS)

    for grant in stock["grants"]:
        grant_values = (
            f"grant:{grant['id']}",
            grant["title"],
            grant["grant_date"],
            grant["quantity"],
            grant["vesting_start_date"],
            grant["schedule_type"],
            grant["customized"],
        )
        for vesting in grant["vestings"] or [None]:
            append_values(
                plans,
                (
                    "rsu_vesting" if vesting else "rsu_grant",
                    *grant_values,
                    f"vesting:{vesting['id']}" if vesting else None,
                    vesting["date"] if vesting else None,
                    vesting["quantity"] if vesting else None,
                ),
            )
    for purchase in stock["purchases"]:
        append_values(
            plans,
            (
                "stock_purchase",
                None,
                purchase["plan_name"],
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                f"purchase:{purchase['id']}",
                purchase["purchase_date"],
                purchase["quantity"],
            ),
        )
    format_table(plans, PLANS_HEADERS, 6)

    sales = workbook.create_sheet("Sales")
    append_values(sales, SALES_HEADERS)
    for sale in stock["sales"]:
        allocations = sorted(
            sale["allocations"],
            key=lambda allocation: (
                "purchase_id" in allocation,
                allocation.get("vesting_id", allocation.get("purchase_id")),
            ),
        )
        for allocation in allocations or [None]:
            allocation = allocation or {}
            append_values(
                sales,
                (
                    f"sale:{sale['id']}",
                    sale["transaction_date"],
                    sale["quantity"],
                    sale["proceeds_per_share"],
                    sale["currency"],
                    f"vesting:{allocation['vesting_id']}" if "vesting_id" in allocation else None,
                    (
                        f"purchase:{allocation['purchase_id']}"
                        if "purchase_id" in allocation
                        else None
                    ),
                    allocation.get("quantity"),
                ),
            )
    format_table(sales, SALES_HEADERS, 1)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    output.seek(0)
    return output
