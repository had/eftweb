import tomllib
from pathlib import Path

import pytest

from app import create_app
from app.service import tax_service
from app.service.tax_parameters import load_tax_parameters
from easyfrenchtax import TaxField, TaxSimulator
from easyfrenchtax.tax_simulator import TaxParameters, year_tax_parameters

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "app" / "tax_parameters.toml"

# Deliberately independent of the bundled configuration, which evolves each year.
TEST_CONFIG = """\
[2026]
family_quotient_benefices_capping = 1791
slices_thresholds = [11497, 29315, 83823, 180294]
slices_rates = [0.11, 0.30, 0.41, 0.45]
fees_10p_deduction_ceiling = 14426
fees_10p_deduction_floor = 504
"""


@pytest.fixture(autouse=True)
def restore_parameters():
    original = year_tax_parameters.copy()
    yield
    year_tax_parameters.clear()
    year_tax_parameters.update(original)


def test_bundled_parameters_load_all_years_and_preserve_shared_registry():
    original = year_tax_parameters.copy()
    configured = tomllib.loads(DEFAULT_CONFIG.read_text())
    load_tax_parameters(DEFAULT_CONFIG)

    assert tax_service.year_tax_parameters is year_tax_parameters
    for year, values in configured.items():
        year = int(year)
        assert year_tax_parameters[year] == TaxParameters(**values)
        simulator = TaxSimulator(year, {TaxField.SALARY_1_1AJ: 60000})
        assert simulator.parameters is year_tax_parameters[year]
        assert simulator.state[TaxField.YEAR] == year
    assert all(
        year_tax_parameters[year] is values
        for year, values in original.items()
        if str(year) not in configured
    )


def test_startup_loads_custom_file_for_new_and_existing_years(tmp_path, monkeypatch):
    original_2024 = year_tax_parameters[2024]
    custom_values = TEST_CONFIG.replace(
        "[11497, 29315, 83823, 180294]", "[100000, 200000, 300000, 400000]"
    )
    custom_file = tmp_path / "tax_parameters.toml"
    custom_file.write_text(
        custom_values.replace("[2026]", "[2098]") + "\n" + custom_values.replace("[2026]", "[2025]")
    )
    monkeypatch.setenv("TAX_PARAMETERS_FILE", str(custom_file))

    app = create_app("testing")

    assert app.config["TAX_PARAMETERS_FILE"] == str(custom_file)
    assert year_tax_parameters[2024] is original_2024
    for year in (2025, 2098):
        simulator = TaxSimulator(year, {TaxField.SALARY_1_1AJ: 60000})
        assert simulator.parameters is year_tax_parameters[year]
        assert simulator.state[TaxField.NET_TAXES] == 0


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("[2026]", "[income_2025]"),
        ("fees_10p_deduction_floor = 504", ""),
        ("fees_10p_deduction_floor = 504", "fees_10p_deduction_floor = 504\nunknown = 1"),
        ("family_quotient_benefices_capping = 1791", "family_quotient_benefices_capping = true"),
        ("family_quotient_benefices_capping = 1791", "family_quotient_benefices_capping = nan"),
        ("[11497, 29315, 83823, 180294]", "[29315, 11497, 83823, 180294]"),
        ("[11497, 29315, 83823, 180294]", "[]"),
        ("[0.11, 0.30, 0.41, 0.45]", "[0.11]"),
        ("[0.11, 0.30, 0.41, 0.45]", "[11, 30, 41, 45]"),
        ("fees_10p_deduction_floor = 504", "fees_10p_deduction_floor = -1"),
        ("fees_10p_deduction_floor = 504", "fees_10p_deduction_floor = 20000"),
    ],
)
def test_invalid_config_does_not_partially_update_registry(tmp_path, before, after):
    original = year_tax_parameters.copy()
    content = TEST_CONFIG
    assert before in content
    custom_file = tmp_path / "tax_parameters.toml"
    custom_file.write_text(
        content.replace("[2026]", "[2098]") + "\n" + content.replace(before, after)
    )

    with pytest.raises(ValueError, match="Invalid tax parameters"):
        load_tax_parameters(custom_file)

    assert year_tax_parameters == original


def test_startup_rejects_missing_custom_config(tmp_path, monkeypatch):
    monkeypatch.setenv("TAX_PARAMETERS_FILE", str(tmp_path / "missing.toml"))

    with pytest.raises(FileNotFoundError):
        create_app("testing")
