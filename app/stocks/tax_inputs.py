"""Exact monetary inputs shared by ledger entry, imports and tax calculations."""

from decimal import ROUND_FLOOR, Decimal, InvalidOperation

from app import db


def amount(value, label, places=6, allow_zero=True):
    try:
        if (
            isinstance(value, bool)
            or value is None
            or not isinstance(value, (str, int, float, Decimal))
        ):
            raise InvalidOperation()
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result >= 100_000_000:
            raise InvalidOperation()
        if not allow_zero and result == 0:
            raise InvalidOperation()
        if result != result.quantize(Decimal(10) ** -places):
            raise InvalidOperation()
        return result
    except (InvalidOperation, ValueError):
        raise ValueError(
            f"{label} must be {'non-negative' if allow_zero else 'positive'}, below 100,000,000, with at most {places} decimals"
        ) from None


def split_cents(total, weights):
    """Largest-remainder allocation; input order breaks ties and cents are conserved."""
    total = Decimal(total)
    weights = [Decimal(w) for w in weights]
    if not weights:
        return []
    denominator = sum(weights)
    if denominator <= 0:
        raise ValueError("Fee allocation requires positive proceeds")
    raw = [total * 100 * w / denominator for w in weights]
    cents = [int(v.to_integral_value(rounding=ROUND_FLOOR)) for v in raw]
    remainder = int(total * 100) - sum(cents)
    for i in sorted(range(len(raw)), key=lambda i: (-(raw[i] - cents[i]), i))[:remainder]:
        cents[i] += 1
    return [Decimal(v) / 100 for v in cents]


def apply_fmv(stock_id, allocations, require=True):
    """Populate acquisition values only as part of a new sale's transaction."""
    from .models import GrantVesting, StockGrant, StockPurchase

    for row in allocations:
        if "vesting_id" in row:
            lot = (
                db.session.query(GrantVesting)
                .join(StockGrant)
                .filter(GrantVesting.id == row["vesting_id"], StockGrant.stock_id == stock_id)
                .first()
            )
        else:
            lot = StockPurchase.query.filter_by(id=row["purchase_id"], stock_id=stock_id).first()
        if lot is None:
            raise ValueError("Acquisition lot not found for this stock")
        supplied = row.pop("acquisition_fmv", None)
        current = lot.acquisition_fmv or Decimal(0)
        if supplied is None:
            if require and not current:
                raise ValueError(f"Acquisition FMV is required for lot {lot.id}")
            continue
        proposed = amount(supplied, "Acquisition FMV", allow_zero=not require)
        if current and proposed != current:
            raise ValueError(f"Acquisition FMV conflicts with the recorded value for lot {lot.id}")
        lot.acquisition_fmv = proposed
