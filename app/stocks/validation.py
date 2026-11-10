"""Shared validation for manual stock entry and workbook imports."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from app.constants import JAVASCRIPT_MAX_SAFE_INTEGER


def calendar_date(value, label):
    try:
        parsed = date.fromisoformat(value) if isinstance(value, str) else None
        if parsed is None or parsed.isoformat() != value:
            raise ValueError()
    except ValueError:
        raise ValueError(f"{label} must be a valid date in YYYY-MM-DD format") from None
    return parsed


def positive_quantity(value, label):
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 < value <= JAVASCRIPT_MAX_SAFE_INTEGER
    ):
        raise ValueError(
            f"{label} must be a positive whole number of shares within the safe integer range"
        )
    return value


def sale_payload(data, allow_empty=False):
    if not isinstance(data, dict):
        raise ValueError("Sale data must be an object")
    transaction_date = calendar_date(data.get("transaction_date"), "Transaction date")
    if transaction_date > datetime.now(ZoneInfo("Europe/Paris")).date():
        raise ValueError("Transaction date cannot be in the future")
    quantity = positive_quantity(data.get("quantity"), "Sale quantity")
    value = data.get("proceeds_per_share")
    try:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise InvalidOperation()
        price = Decimal(str(value))
        if not price.is_finite() or not 0 < price < 100_000_000:
            raise InvalidOperation()
        if price != price.quantize(Decimal("0.000001")):
            raise InvalidOperation()
    except InvalidOperation:
        raise ValueError(
            "Proceeds per share must be positive, below 100,000,000 USD, with at most six decimals"
        ) from None
    if data.get("currency", "USD") != "USD":
        raise ValueError("Only USD sales are supported")
    rows = data.get("allocations")
    if not isinstance(rows, list) or (not rows and not allow_empty):
        raise ValueError("Allocate shares to at least one acquisition lot")
    allocations = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each allocation must be an object")
        sources = [key for key in ("vesting_id", "purchase_id") if key in row]
        if len(sources) != 1:
            raise ValueError("Each allocation must identify exactly one vesting or purchase")
        source = sources[0]
        source_id = positive_quantity(row[source], "Acquisition ID")
        key = (source, source_id)
        if key in seen:
            raise ValueError("Each acquisition lot can appear only once")
        seen.add(key)
        allocations.append(
            {
                source: source_id,
                "quantity": positive_quantity(row.get("quantity"), "Allocated quantity"),
            }
        )
    if (allocations or not allow_empty) and sum(row["quantity"] for row in allocations) != quantity:
        raise ValueError("Allocated shares must exactly match the sale quantity")
    return {
        "transaction_date": transaction_date.isoformat(),
        "quantity": quantity,
        "proceeds_per_share": format(price, ".6f"),
        "currency": "USD",
        # Preserve legacy RSU canonicalization so existing retry hashes remain valid.
        "allocations": sorted(
            allocations,
            key=lambda row: ("purchase_id" in row, row.get("vesting_id", row.get("purchase_id"))),
        ),
    }


def grant_number_value(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value.strip()) > 256:
        raise ValueError("Grant number must be text of at most 256 characters")
    return value.strip() or None


def allocation_error(data, pockets, used):
    for row in data["allocations"]:
        source = "vesting_id" if "vesting_id" in row else "purchase_id"
        key = (source, row[source])
        pocket = pockets.get(key)
        if pocket is None:
            return "Acquisition lot not found for this stock", 400
        acquired_date, quantity = pocket
        if acquired_date.isoformat() > data["transaction_date"]:
            return "Shares must have been acquired by the transaction date", 400
        if row["quantity"] > quantity - used.get(key, 0):
            return (
                "An acquisition lot no longer has enough available shares. Reload to review its balance.",
                409,
            )
    return None


def grant_payload(data, stock, allow_empty=False):
    if not isinstance(data, dict):
        raise ValueError("Grant data must be an object")
    grant_date = calendar_date(data.get("grant_date"), "Grant date")
    title = data.get("title", "")
    if not isinstance(title, str) or len(title.strip()) > 256:
        raise ValueError("Grant title must be a string of at most 256 characters")
    title = title.strip() or f"{stock.symbol}-{grant_date.isoformat()}"
    quantity = positive_quantity(data.get("quantity"), "Granted quantity")
    start_date = calendar_date(data.get("vesting_start_date"), "Vesting reference date")
    schedule_type = data.get("schedule_type")
    if schedule_type not in ("quarterly", "cliff-quarterly"):
        raise ValueError("Choose a valid vesting schedule")
    customized = data.get("customized")
    if not isinstance(customized, bool):
        raise ValueError("customized must be a boolean")
    rows = data.get("vestings")
    if not isinstance(rows, list) or (not rows and not allow_empty):
        raise ValueError("Add at least one vesting release")
    releases = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each vesting release must be an object")
        releases.append(
            {
                "date": calendar_date(row.get("date"), "Release date").isoformat(),
                "quantity": positive_quantity(row.get("quantity"), "Release quantity"),
            }
        )
    if (releases or not allow_empty) and sum(row["quantity"] for row in releases) != quantity:
        raise ValueError("Scheduled shares must exactly match the granted quantity")
    number = grant_number_value(data.get("grant_number"))
    return {
        **({"grant_number": number} if number is not None else {}),
        "title": title,
        "grant_date": grant_date.isoformat(),
        "quantity": quantity,
        "vesting_start_date": start_date.isoformat(),
        "schedule_type": schedule_type,
        "customized": customized,
        "vestings": sorted(releases, key=lambda row: (row["date"], row["quantity"])),
    }


def purchase_payload(data):
    if not isinstance(data, dict):
        raise ValueError("Purchase data must be an object")
    purchase_date = calendar_date(data.get("purchase_date"), "Purchase date")
    if purchase_date > datetime.now(ZoneInfo("Europe/Paris")).date():
        raise ValueError("Purchase date cannot be in the future")
    quantity = positive_quantity(data.get("quantity"), "Purchased quantity")
    plan_name = data.get("plan_name", "ESPP")
    if not isinstance(plan_name, str) or not plan_name.strip() or len(plan_name.strip()) > 256:
        raise ValueError("Plan name must be a nonempty string of at most 256 characters")
    return {
        "purchase_date": purchase_date.isoformat(),
        "quantity": quantity,
        "plan_name": plan_name.strip(),
    }
