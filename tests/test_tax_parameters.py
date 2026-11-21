from pathlib import Path

import pytest
from easyfrenchtax import TaxField, TaxSimulator
from easyfrenchtax.tax_simulator import year_tax_parameters

from app import create_app
from app.service import tax_service
from app.service.tax_parameters import load_tax_parameters

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "app" / "tax_parameters.toml"


@pytest.fixture(autouse=True)
def restore_parameters():
    original = year_tax_parameters.copy()
    yield
    year_tax_parameters.clear()
    year_tax_parameters.update(original)


def test_bundled_2026_parameters_copy_2025_and_preserve_shared_registry():
    original = year_tax_parameters.copy()
    load_tax_parameters(DEFAULT_CONFIG)

    assert tax_service.year_tax_parameters is year_tax_parameters
    assert year_tax_parameters[2026] == year_tax_parameters[2025]
    assert all(year_tax_parameters[year] == values for year, values in original.items())
    simulator = TaxSimulator(2026, {TaxField.SALARY_1_1AJ: 60000})
    assert simulator.parameters is year_tax_parameters[2026]
    assert simulator.state[TaxField.YEAR] == 2026


def test_startup_loads_custom_file_for_new_and_existing_years(tmp_path, monkeypatch):
    original_2024 = year_tax_parameters[2024]
    custom_values = DEFAULT_CONFIG.read_text().replace(
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
    content = DEFAULT_CONFIG.read_text()
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
