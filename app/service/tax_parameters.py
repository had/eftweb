"""Load filing-year parameters into easyfrenchtax's shared registry."""

import math
import tomllib
from itertools import pairwise

from easyfrenchtax.tax_simulator import TaxParameters, year_tax_parameters


def _is_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _validate_parameters(values):
    if not isinstance(values, dict) or set(values) != set(TaxParameters._fields):
        raise ValueError(f"expected exactly these fields: {', '.join(TaxParameters._fields)}")

    thresholds = values["slices_thresholds"]
    rates = values["slices_rates"]
    if (
        not isinstance(thresholds, list)
        or not thresholds
        or not all(_is_number(value) and value > 0 for value in thresholds)
        or any(left >= right for left, right in pairwise(thresholds))
    ):
        raise ValueError("slices_thresholds must be a strictly increasing list of positive numbers")
    if (
        not isinstance(rates, list)
        or len(rates) != len(thresholds)
        or not all(_is_number(value) and 0 <= value <= 1 for value in rates)
    ):
        raise ValueError("slices_rates must match the thresholds and contain rates between 0 and 1")

    for field in (
        "family_quotient_benefices_capping",
        "fees_10p_deduction_ceiling",
        "fees_10p_deduction_floor",
    ):
        if not _is_number(values[field]) or values[field] < 0:
            raise ValueError(f"{field} must be a nonnegative number")
    if values["fees_10p_deduction_floor"] > values["fees_10p_deduction_ceiling"]:
        raise ValueError("fees_10p_deduction_floor must not exceed fees_10p_deduction_ceiling")

    return TaxParameters(**values)


def load_tax_parameters(path):
    """Validate all configured years, then add or override entries in place.

    Call during startup, before serving requests, in every server worker.
    Unlisted years keep their library parameters. Invalid files abort startup.
    """
    with open(path, "rb") as config_file:
        configured_years = tomllib.load(config_file)

    parameters = {}
    for year, values in configured_years.items():
        try:
            if not year.isdecimal() or len(year) != 4:
                raise ValueError("section keys must be four-digit filing years")
            parameters[int(year)] = _validate_parameters(values)
        except ValueError as error:
            raise ValueError(
                f"Invalid tax parameters in {path}, filing year {year}: {error}"
            ) from error

    # Keep the same object so existing imports (including tax_service) see updates.
    year_tax_parameters.update(parameters)
