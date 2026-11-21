"""Format-independent preview, availability checks, and atomic import writes."""

from collections import defaultdict
from copy import deepcopy
from datetime import date
from decimal import Decimal
from uuid import uuid4

from app import db

from .import_parsers import fingerprint
from .models import GrantVesting, StockGrant, StockPurchase, StockSale, StockSaleAllocation
from .tax_inputs import amount, apply_fmv, split_cents
from .validation import allocation_error, sale_payload


def stock_snapshot(stock):
    return {
        **stock.to_dict(),
        "family_archived": stock.family.is_archived,
        "grants": [grant.to_dict() for grant in stock.grants],
        "purchases": [purchase.to_dict() for purchase in stock.purchases],
        "sales": [sale.to_dict() for sale in stock.sales],
    }


def acquisition_lots(snapshot):
    used = defaultdict(int)
    for sale in snapshot["sales"]:
        for allocation in sale["allocations"]:
            source = "vesting_id" if "vesting_id" in allocation else "purchase_id"
            used[(source, allocation[source])] += allocation["quantity"]
    lots = []
    for grant in snapshot["grants"]:
        for vesting in grant["vestings"]:
            lots.append(
                {
                    "source": "vesting_id",
                    "id": vesting["id"],
                    "date": vesting["date"],
                    "quantity": vesting["quantity"],
                    "plan_type": "RS",
                    "grant_number": grant.get("grant_number"),
                    "grant_date": grant["grant_date"],
                    "label": f"{grant['title']} · {vesting['date']} · {vesting['quantity']} shares",
                    "acquisition_fmv": vesting.get("acquisition_fmv", "0.000000"),
                    "available": vesting["quantity"] - used[("vesting_id", vesting["id"])],
                }
            )
    for purchase in snapshot["purchases"]:
        lots.append(
            {
                "source": "purchase_id",
                "id": purchase["id"],
                "date": purchase["purchase_date"],
                "quantity": purchase["quantity"],
                "plan_type": "ESPP",
                "plan_name": purchase["plan_name"],
                "label": f"{purchase['plan_name']} · {purchase['purchase_date']} · {purchase['quantity']} shares",
                "acquisition_fmv": purchase.get("acquisition_fmv", "0.000000"),
                "available": purchase["quantity"] - used[("purchase_id", purchase["id"])],
            }
        )
    return lots


def source_group(sale):
    return tuple(
        sale.get(key)
        for key in (
            "import_source",
            "source_order_number",
            "transaction_date",
            "proceeds_per_share",
            "currency",
        )
    )


def automatic_allocations(sale, lots):
    quantities = defaultdict(int)
    issues = []
    for source in sale["sources"]:
        candidates = [
            lot
            for lot in lots
            if lot["date"] == source["date"]
            and (
                lot["source"] == "vesting_id"
                and source["plan_type"] == "RS"
                and lot.get("grant_number") == source.get("grant_number")
                or lot["source"] == "purchase_id"
                and source["plan_type"] == "ESPP"
                and lot["plan_name"].strip().upper() == "ESPP"
            )
        ]
        if len(candidates) != 1:
            descriptor = (
                f"grant {source.get('grant_number')} vesting"
                if source["plan_type"] == "RS"
                else "ESPP purchase"
            )
            issues.append(f"No unique {descriptor} on {source['date']}; select existing lots")
            continue
        lot = candidates[0]
        quantities[(lot["source"], lot["id"])] += source["quantity"]
        if source["acquired_date"] != lot["date"]:
            issues.append(
                f"Broker acquisition date {source['acquired_date']} differs from the selected lot"
            )
        if source["plan_type"] == "RS" and source["grant_date"] != lot["grant_date"]:
            issues.append(
                f"Broker grant date {source['grant_date']} differs from the selected grant"
            )
    return [
        {source: source_id, "quantity": quantity}
        for (source, source_id), quantity in quantities.items()
    ], issues


def validate_decisions(parsed, decisions):
    if not isinstance(decisions, dict):
        raise ValueError("Import decisions must be an object")
    known = {sale["key"] for sale in parsed["sales"]}
    if set(decisions) - known or (parsed["format"] == "eftweb" and decisions):
        raise ValueError("Import decisions do not match this workbook")
    for decision in decisions.values():
        if not isinstance(decision, dict) or set(decision) - {
            "skip",
            "allocations",
            "reviewed",
            "order_fee",
        }:
            raise ValueError("Invalid sale decision")
        for field in ("skip", "reviewed"):
            if field in decision and type(decision[field]) is not bool:
                raise ValueError(f"{field} must be a boolean")


def prepare_import(parsed, snapshot, decisions=None, confirming=False):
    decisions = {} if decisions is None else decisions
    validate_decisions(parsed, decisions)
    view = {
        "format": parsed["format"],
        "stock_revision": fingerprint(snapshot),
        "stock_name": parsed.get("name", snapshot["name"]),
        "symbol": parsed["symbol"],
        "counts": {key: len(parsed[key]) for key in ("grants", "purchases", "sales")},
        "grants": parsed["grants"],
        "purchases": parsed["purchases"],
        "ignored": parsed["ignored"],
        "errors": [],
        "sales": [],
        "lots": [],
    }
    if parsed["symbol"] and parsed["symbol"] != snapshot["symbol"]:
        view["errors"].append("The workbook ticker does not match this stock")
    if parsed["format"] == "eftweb":
        if any(snapshot[key] for key in ("grants", "purchases", "sales")):
            view["errors"].append("App exports can only be restored into an empty stock")
        view["sales"] = [
            {**sale, "status": "ready", "warnings": [], "errors": [], "skip": False}
            for sale in parsed["sales"]
        ]
        # Reject colliding broker provenance before hitting a database constraint.
        groups = [source_group(sale) for sale in parsed["sales"] if sale.get("import_source")]
        if len(groups) != len(set(groups)):
            view["errors"].append("Duplicate broker order groups in app export")
        view["can_import"] = not view["errors"]
        return view

    lots = acquisition_lots(snapshot)
    view["lots"] = lots
    pockets = {
        (lot["source"], lot["id"]): (date.fromisoformat(lot["date"]), lot["quantity"])
        for lot in lots
    }
    used = {(lot["source"], lot["id"]): lot["quantity"] - lot["available"] for lot in lots}
    order_fees = {}
    for original in parsed["sales"]:
        if original.get("source_order_number") and "order_fee" in decisions.get(
            original["key"], {}
        ):
            order = original["source_order_number"]
            fee = amount(decisions[original["key"]]["order_fee"], "Order fee", places=2)
            if order in order_fees and fee != order_fees[order]:
                raise ValueError("Provide one consistent fee per broker order")
            order_fees[order] = fee
    allocated_fees = {}
    for order, fee in order_fees.items():
        executions = [
            s
            for s in parsed["sales"]
            if s.get("source_order_number") == order and s.get("quantity")
        ]
        weights = [Decimal(s["proceeds_per_share"]) * s["quantity"] for s in executions]
        allocated_fees.update(
            (s["key"], format(v, ".2f"))
            for s, v in zip(executions, split_cents(fee, weights), strict=True)
        )
    proposed_fmvs = {}
    existing_groups = {
        source_group(sale): sale for sale in snapshot["sales"] if sale.get("import_source")
    }
    for original in parsed["sales"]:
        sale = deepcopy(original)
        decision = decisions.get(sale["key"], {})
        sale["fees"] = allocated_fees.get(sale["key"], "0.00")
        sale.update(
            skip=decision.get("skip", False),
            reviewed=decision.get("reviewed", False),
            status="ready",
        )
        if sale["errors"]:
            sale["status"] = "invalid"
            view["sales"].append(sale)
            continue
        existing = existing_groups.get(source_group(sale))
        if existing:
            sale["existing_sale_id"] = existing["id"]
            if existing["source_fingerprint"] == sale["source_fingerprint"]:
                sale.update(status="duplicate", skip=True)
            else:
                sale.update(
                    status="conflict",
                    errors=[
                        "This broker order group already exists with different facts. Skip it or correct the saved sale first."
                    ],
                )
            view["sales"].append(sale)
            continue
        if sale["skip"]:
            view["sales"].append(sale)
            continue
        auto, matching_issues = automatic_allocations(sale, lots)
        sale["allocations"] = decision.get("allocations", auto)
        try:
            sale["allocations"] = sale_payload(sale)["allocations"]
        except ValueError as error:
            sale.update(status="needs_review", matching_issues=matching_issues)
            sale["errors"].append(str(error))
            view["sales"].append(sale)
            continue
        # Source FMV follows its exact automatic lot mapping; manual splits must supply their FMVs.
        source_values = {}
        for source in sale["sources"]:
            matched, _ = automatic_allocations({"sources": [source]}, lots)
            for row in matched:
                column = "vesting_id" if "vesting_id" in row else "purchase_id"
                source_values[(column, row[column])] = source.get("acquisition_fmv")
        enriched = []
        for row in sale["allocations"]:
            row = dict(row)
            column = "vesting_id" if "vesting_id" in row else "purchase_id"
            value = row.get("acquisition_fmv") or source_values.get((column, row.get(column)))
            if not value:
                value = next(
                    (
                        lot.get("acquisition_fmv")
                        for lot in lots
                        if lot["source"] == column and lot["id"] == row.get(column)
                    ),
                    None,
                )
            if value and Decimal(value) > 0:
                row["acquisition_fmv"] = value
            enriched.append(row)
        sale["allocations"] = enriched
        sale["matching_issues"] = matching_issues
        possible = [
            saved["id"]
            for saved in snapshot["sales"]
            if not saved.get("import_source")
            and all(
                saved[key] == sale[key]
                for key in ("transaction_date", "quantity", "proceeds_per_share", "currency")
            )
        ]
        sale["possible_duplicate_ids"] = possible
        if any(
            saved.get("import_source") == "etrade"
            and saved.get("source_order_number") == sale["source_order_number"]
            for saved in snapshot["sales"]
        ):
            sale["warnings"].append(
                "Other executions of this broker order are already recorded. Review this additional price/date group."
            )
        if possible:
            sale["warnings"].append(
                "Possible duplicate of manually recorded sale(s): " + ", ".join(map(str, possible))
            )
        needs_review = bool(matching_issues or sale["warnings"] or "allocations" in decision)
        if not sale["skip"]:
            try:
                normalized = sale_payload(sale)
                # Manual resolution can split lots, but cannot switch acquisition type.
                permitted = {
                    "vesting_id" if source["plan_type"] == "RS" else "purchase_id"
                    for source in sale["sources"]
                }
                if any(
                    ("vesting_id" if "vesting_id" in row else "purchase_id") not in permitted
                    for row in normalized["allocations"]
                ):
                    raise ValueError("Selected lots do not match the broker's acquisition type")
                for plan_type, column in (("RS", "vesting_id"), ("ESPP", "purchase_id")):
                    expected = sum(
                        source["quantity"]
                        for source in sale["sources"]
                        if source["plan_type"] == plan_type
                    )
                    if (
                        sum(row["quantity"] for row in normalized["allocations"] if column in row)
                        != expected
                    ):
                        raise ValueError(
                            "Allocations must preserve the RSU and ESPP share quantities"
                        )
                error = allocation_error(normalized, pockets, used)
                if error:
                    raise ValueError(error[0])
                for row in normalized["allocations"]:
                    value = amount(row.get("acquisition_fmv"), "Acquisition FMV", allow_zero=False)
                    column = "vesting_id" if "vesting_id" in row else "purchase_id"
                    identity = (column, row[column])
                    recorded = next(
                        Decimal(lot["acquisition_fmv"])
                        for lot in lots
                        if lot["source"] == column and lot["id"] == row[column]
                    )
                    if recorded and value != recorded:
                        raise ValueError("Acquisition FMV conflicts with the recorded lot value")
                    if identity in proposed_fmvs and proposed_fmvs[identity] != value:
                        raise ValueError(
                            "Conflicting acquisition FMVs for the same lot in this import"
                        )
                    proposed_fmvs[identity] = value
                sale["allocations"] = normalized["allocations"]
                if confirming or not needs_review:
                    for allocation in sale["allocations"]:
                        source = "vesting_id" if "vesting_id" in allocation else "purchase_id"
                        key = (source, allocation[source])
                        used[key] = used.get(key, 0) + allocation["quantity"]
            except ValueError as error:
                sale["errors"].append(str(error))
        if sale["errors"] or (needs_review and not sale["reviewed"]):
            sale["status"] = "needs_review"
        view["sales"].append(sale)
    view["can_import"] = not view["errors"] and all(
        sale["skip"] or sale["status"] == "ready" for sale in view["sales"]
    )
    return view


def bookkeeping(data):
    return {"creation_token": str(uuid4()), "request_hash": fingerprint(data)}


def persist_import(stock, parsed, preview):
    counts = {"grants": 0, "vestings": 0, "purchases": 0, "sales": 0, "skipped_sales": 0}
    lots = {}
    if parsed["format"] == "eftweb":
        stock.name = parsed["name"]
        for data in parsed["grants"]:
            fields = {
                key: data[key]
                for key in (
                    "title",
                    "quantity",
                    "vesting_start_date",
                    "grant_date",
                    "schedule_type",
                    "customized",
                )
            }
            fields.update(
                grant_date=date.fromisoformat(fields["grant_date"]),
                vesting_start_date=date.fromisoformat(fields["vesting_start_date"]),
            )
            role = data.get("taxpayer_role")
            if role and not getattr(stock.family, role, None):
                raise ValueError(f"Imported grant {role} is not present in this family")
            grant = StockGrant(
                stock_id=stock.id,
                **fields,
                grant_number=data.get("grant_number"),
                approval_date=(
                    date.fromisoformat(data["approval_date"]) if data.get("approval_date") else None
                ),
                taxpayer_role=data.get("taxpayer_role"),
                **bookkeeping(data),
            )
            for vesting in data["vestings"]:
                row = GrantVesting(
                    date=date.fromisoformat(vesting["date"]),
                    quantity=vesting["quantity"],
                    acquisition_fmv=Decimal(vesting.get("acquisition_fmv", "0")),
                )
                grant.vestings.append(row)
                lots[vesting["key"]] = ("vesting_id", row)
                counts["vestings"] += 1
            db.session.add(grant)
            counts["grants"] += 1
        for data in parsed["purchases"]:
            purchase = StockPurchase(
                stock_id=stock.id,
                plan_name=data["plan_name"],
                acquisition_fmv=Decimal(data.get("acquisition_fmv", "0")),
                quantity=data["quantity"],
                purchase_date=date.fromisoformat(data["purchase_date"]),
                **bookkeeping(data),
            )
            db.session.add(purchase)
            lots[data["key"]] = ("purchase_id", purchase)
            counts["purchases"] += 1
        db.session.flush()
    for data in preview["sales"]:
        if data["skip"]:
            counts["skipped_sales"] += 1
            continue
        allocations = data["allocations"]
        if parsed["format"] == "eftweb":
            allocations = [
                {
                    lots[row["source_key"]][0]: lots[row["source_key"]][1].id,
                    "quantity": row["quantity"],
                }
                for row in allocations
            ]
        if parsed["format"] == "etrade":
            apply_fmv(stock.id, allocations)
        sale = StockSale(
            stock_id=stock.id,
            transaction_date=date.fromisoformat(data["transaction_date"]),
            quantity=data["quantity"],
            proceeds_per_share=Decimal(data["proceeds_per_share"]),
            currency=data["currency"],
            fees=Decimal(data.get("fees", "0")),
            **{
                key: data.get(key)
                for key in ("import_source", "source_order_number", "source_fingerprint")
            },
            **bookkeeping(data),
            allocations=[StockSaleAllocation(**row) for row in allocations],
        )
        db.session.add(sale)
        counts["sales"] += 1
    return counts
