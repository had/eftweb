from collections import defaultdict
from decimal import Decimal

from easyfrenchtax import TaxField, TaxInfoFlag, TaxSimulator
from easyfrenchtax.tax_simulator import tax_round, year_tax_parameters

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


def _calculation_details(simulator):
    """Describe the simulator's scale and caps using its active year parameters."""
    state = simulator.state
    shares = state[TaxField.HOUSEHOLD_SHARES]
    taxable_income = max(float(state[TaxField.TAXABLE_INCOME]), 0)
    thresholds = [float(value * shares) for value in simulator.parameters.slices_thresholds]
    rates = [0, *simulator.parameters.slices_rates]
    brackets = []
    lower = 0
    scale_tax = 0
    for upper, rate in zip([*thresholds, None], rates, strict=True):
        income = (
            max(min(taxable_income, upper) - lower, 0)
            if upper is not None
            else max(taxable_income - lower, 0)
        )
        tax = income * rate
        scale_tax += tax
        brackets.append(
            {
                "lower_bound": lower,
                "upper_bound": upper,
                "rate": rate,
                "income": tax_round(income, 2),
                "tax": tax_round(tax, 2),
            }
        )
        lower = upper

    donation_75 = float(state[TaxField.CHARITY_DONATION_7UD])
    donation_75_eligible = min(donation_75, 1000)
    transferred = max(donation_75 - 1000, 0)
    donation_66 = float(state[TaxField.CHARITY_DONATION_7UF]) + transferred
    donation_66_limit = taxable_income * 0.2
    # Match the library's whole-euro rounding of the 66% donation base.
    donation_66_eligible = tax_round(min(donation_66, donation_66_limit))

    # The library's textual flag can be negative when donations exceed tax.
    # Use a nonnegative base so this meter never reports negative usage.
    tax_after_donations = max(
        state[TaxField.TAX_BEFORE_REDUCTIONS] - state[TaxField.CHARITY_REDUCTION], 0
    )
    advantages = (
        min(state[TaxField.SME_SUBSCRIPTION_REDUCTION], tax_after_donations)
        + state[TaxField.CHILDREN_DAYCARE_TAXCREDIT]
        + state[TaxField.HOME_SERVICES_TAXCREDIT]
    )

    return {
        "progressive_tax": {
            "taxable_income": taxable_income,
            "brackets": brackets,
            "scale_tax": tax_round(scale_tax),
        },
        "donation_buckets": [
            {
                "rate": 0.75,
                "donated": donation_75,
                "eligible": donation_75_eligible,
                "limit": 1000,
                "reduction": tax_round(donation_75_eligible * 0.75, 2),
                "overflow": transferred,
            },
            {
                "rate": 0.66,
                "donated": donation_66,
                "eligible": donation_66_eligible,
                "limit": tax_round(donation_66_limit, 2),
                "reduction": tax_round(donation_66_eligible * 0.66, 2),
                "overflow": tax_round(max(donation_66 - donation_66_limit, 0), 2),
            },
        ],
        "fiscal_advantages": {
            "limit": 10000,
            "used": tax_round(min(advantages, 10000), 2),
            "excess": tax_round(max(advantages - 10000, 0), 2),
        },
    }


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
    simulator = TaxSimulator(tax_return.year, tax_input, debug=False)
    tax_result = simulator.state
    return {
        "net_taxes": float(tax_result[TaxField.NET_TAXES]),
        "net_social_taxes": float(tax_result[TaxField.NET_SOCIAL_TAXES]),
        "reference_fiscal_income": float(tax_result[TaxField.REFERENCE_FISCAL_INCOME]),
        "household_shares": float(tax_result[TaxField.HOUSEHOLD_SHARES]),
        "marginal_tax_rate": float(simulator.flags[TaxInfoFlag.MARGINAL_TAX_RATE].rstrip("%"))
        / 100,
        **_calculation_details(simulator),
    }
