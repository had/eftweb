from collections import defaultdict
from decimal import Decimal

from easyfrenchtax import TaxField, TaxSimulator
from easyfrenchtax.tax_simulator import year_tax_parameters

from app import db
from app.family.donation_types import DONATION_TYPES_BY_CODE
from app.family.models import TaxReturn


class TaxEstimationError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def _prepare_tax_input(family, income_statements, donation_statements, ifu_statements):
    """Aggregate supported statement amounts without querying or creating forms."""
    amounts = defaultdict(Decimal)
    salary_fields = {
        "taxpayer1": TaxField.SALARY_1_1AJ,
        "taxpayer2": TaxField.SALARY_2_1BJ,
    }
    donation_fields = {
        "7UD": TaxField.CHARITY_DONATION_7UD,
        "7UF": TaxField.CHARITY_DONATION_7UF,
    }
    ifu_fields = {
        "box_2tr": TaxField.FIXED_INCOME_INTERESTS_2TR,
        "box_2bh": TaxField.FIXED_INCOME_INTERESTS_ALREADY_TAXED_2BH,
        "box_2ck": TaxField.INTEREST_TAX_ALREADY_PAID_2CK,
    }

    for statement in income_statements:
        amounts[salary_fields[statement.taxpayer_role]] += (
            statement.known_employment_income or Decimal(0)
        )
    for statement in donation_statements:
        box = DONATION_TYPES_BY_CODE[statement.donation_type]["tax_return_box"]
        if box in donation_fields:
            amounts[donation_fields[box]] += statement.amount or Decimal(0)
    for statement in ifu_statements:
        for attribute, field in ifu_fields.items():
            amounts[field] += getattr(statement, attribute) or Decimal(0)

    tax_input = {field: float(amount) for field, amount in amounts.items()}
    tax_input[TaxField.MARRIED] = family.taxpayer2 is not None
    tax_input[TaxField.NB_CHILDREN] = len(family.children)
    for index, child in enumerate(family.children, start=1):
        tax_input[TaxField(f"child_{index}_birthyear")] = child.date_of_birth.year
    return tax_input


def estimate_tax(tax_return_id):
    """Estimate an active return using supported fields and filing-year rates."""
    tax_return = db.session.get(TaxReturn, tax_return_id)
    if tax_return is None:
        raise TaxEstimationError("Tax return not found", 404)
    if tax_return.is_archived or tax_return.family.is_archived:
        raise TaxEstimationError("Tax return or family is archived", 410)
    if tax_return.year not in year_tax_parameters:
        raise TaxEstimationError(
            f"Tax estimation is unavailable for filing year {tax_return.year}", 422
        )

    tax_input = _prepare_tax_input(
        tax_return.family,
        tax_return.income_statements if tax_return.has_income_statements else [],
        tax_return.donation_statements if tax_return.has_donation_statements else [],
        tax_return.ifu_statements if tax_return.has_investment_statements else [],
    )
    tax_result = TaxSimulator(tax_return.year, tax_input, debug=False).state
    return {
        "net_taxes": float(tax_result[TaxField.NET_TAXES]),
        "net_social_taxes": float(tax_result[TaxField.NET_SOCIAL_TAXES]),
    }
