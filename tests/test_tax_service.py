from datetime import date
from decimal import Decimal

import pytest
from easyfrenchtax import TaxField, TaxSimulator
from easyfrenchtax.tax_simulator import TaxParameters

from app import create_app, db
from app.family.models import (
    DonationStatement,
    Family,
    FamilyMember,
    IfuStatement,
    IncomeStatement,
    TaxReturn,
)
from app.service import tax_service
from app.service.tax_service import _calculation_details, _prepare_tax_input, estimate_tax
from app.stocks import models as stock_models  # noqa: F401 — register Family's stock relationship


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_prepare_tax_input_aggregates_supported_fields_and_household():
    family = Family(members=[
        FamilyMember(role="taxpayer1", position=1, date_of_birth=date(1980, 1, 1)),
        FamilyMember(role="taxpayer2", position=1, date_of_birth=date(1981, 1, 1)),
        FamilyMember(role="child", position=1, date_of_birth=date(2010, 1, 1)),
        FamilyMember(role="child", position=2, date_of_birth=date(2022, 1, 1)),
    ])
    incomes = [
        IncomeStatement(taxpayer_role="taxpayer1", known_employment_income=Decimal("100.10")),
        IncomeStatement(taxpayer_role="taxpayer1", known_employment_income=Decimal("200.20")),
        IncomeStatement(taxpayer_role="taxpayer2", known_employment_income=Decimal("400.45")),
        IncomeStatement(
            taxpayer_role="taxpayer2", known_employment_income=None,
            income_tax_withheld=Decimal("500"),
            supplementary_pension_contributions=Decimal("1000"),
        ),
    ]
    donations = [
        DonationStatement(donation_type="people_in_need", amount=Decimal("20.10")),
        DonationStatement(donation_type="people_in_need", amount=Decimal("30.20")),
        DonationStatement(donation_type="public_interest", amount=Decimal("40.30")),
        DonationStatement(donation_type="election_campaign", amount=Decimal("50.40")),
        *[
            DonationStatement(donation_type=code, amount=Decimal("500"))
            for code in (
                "religious_heritage", "european_people_in_need",
                "european_public_interest", "political_party",
            )
        ],
    ]
    ifus = [
        IfuStatement(
            box_2tr=Decimal("10.10"), box_2bh=Decimal("2.20"), box_2ck=Decimal("3.30"),
            box_2tt=Decimal("100"), box_2dc=Decimal("200"), box_2cg=Decimal("300"),
            box_2df=Decimal("400"), box_2dh=Decimal("500"),
            box_2yy=Decimal("600"), box_2zz=Decimal("700"),
        ),
        IfuStatement(box_2tr=Decimal("20.20"), box_2bh=None, box_2ck=Decimal("4.40")),
    ]

    assert _prepare_tax_input(family, incomes, donations, ifus) == {
        TaxField.SALARY_1_1AJ: 300.30,
        TaxField.SALARY_2_1BJ: 400.45,
        TaxField.CHARITY_DONATION_7UD: 50.30,
        TaxField.CHARITY_DONATION_7UF: 90.70,
        TaxField.FIXED_INCOME_INTERESTS_2TR: 30.30,
        TaxField.FIXED_INCOME_INTERESTS_ALREADY_TAXED_2BH: 2.20,
        TaxField.INTEREST_TAX_ALREADY_PAID_2CK: 7.70,
        TaxField.MARRIED: True,
        TaxField.NB_CHILDREN: 2,
        TaxField.CHILD_1_BIRTHYEAR: 2010,
        TaxField.CHILD_2_BIRTHYEAR: 2022,
    }


def test_prepare_tax_input_handles_empty_single_household():
    assert _prepare_tax_input(Family(), [], [], []) == {
        TaxField.MARRIED: False,
        TaxField.NB_CHILDREN: 0,
    }


@pytest.fixture()
def tax_return(app):
    tax_return = TaxReturn(
        family=Family(), year=2025, has_income_statements=True,
        has_donation_statements=True, has_investment_statements=True,
        income_statements=[IncomeStatement(
            taxpayer_role="taxpayer1", employer_name="Employer",
            known_employment_income=Decimal("60000"),
        )],
        donation_statements=[DonationStatement(
            name="Charity", donation_type="public_interest", amount=Decimal("100"),
        )],
        ifu_statements=[IfuStatement(
            title="Bank", box_2tr=Decimal("1000"), box_2bh=Decimal("100"),
            box_2ck=Decimal("50"),
        )],
    )
    db.session.add(tax_return)
    db.session.commit()
    return tax_return


def test_estimation_endpoint_returns_real_numeric_totals(app, tax_return):
    response = app.test_client().get(f"/api/tax-returns/{tax_return.id}/estimation")
    assert response.status_code == 200
    result = response.get_json()
    assert result["net_taxes"] == 9377.0
    assert result["net_social_taxes"] == 155.0
    assert result["reference_fiscal_income"] == 55000
    assert result["household_shares"] == 1
    assert result["marginal_tax_rate"] == 0.3
    assert sum(band["income"] for band in result["progressive_tax"]["brackets"]) == 54000
    assert result["progressive_tax"]["scale_tax"] == 9365
    assert result["fiscal_advantages"] == {"limit": 10000, "used": 0, "excess": 0}
    assert estimate_tax(tax_return.id) == result


def test_estimation_uses_configured_filing_year_rates(app, tax_return):
    previous = estimate_tax(tax_return.id)
    tax_return.year = 2026  # Filing in 2026 for income earned in 2025.
    db.session.commit()

    response = app.test_client().get(f"/api/tax-returns/{tax_return.id}/estimation")
    assert response.status_code == 200
    result = response.get_json()
    assert result["net_taxes"] == 9316
    assert result["net_social_taxes"] == previous["net_social_taxes"]
    assert result["reference_fiscal_income"] == previous["reference_fiscal_income"]
    assert result["progressive_tax"]["brackets"][0]["upper_bound"] == 11600


@pytest.mark.parametrize("income", [0, 10000, 20000, 50000, 200000, 1000000])
def test_progressive_bands_partition_income_and_contribute_tax(income):
    simulator = TaxSimulator(2025, {})
    simulator.state[TaxField.TAXABLE_INCOME] = income
    simulator.compute_tax_before_reductions()
    progressive = _calculation_details(simulator)["progressive_tax"]
    assert sum(band["income"] for band in progressive["brackets"]) == income
    assert sum(band["tax"] for band in progressive["brackets"]) == pytest.approx(progressive["scale_tax"], abs=0.5)
    assert progressive["brackets"][0]["tax"] == 0
    assert progressive["brackets"][-1]["upper_bound"] is None
    for band in progressive["brackets"]:
        assert band["tax"] == pytest.approx(band["income"] * band["rate"], abs=0.01)


def test_progressive_details_follow_custom_parameters_and_household_shares(monkeypatch):
    monkeypatch.setitem(tax_service.year_tax_parameters, 2098, TaxParameters(
        family_quotient_benefices_capping=1800,
        slices_thresholds=[100, 200], slices_rates=[0.1, 0.2],
        fees_10p_deduction_ceiling=100, fees_10p_deduction_floor=0,
    ))
    simulator = TaxSimulator(2098, {
        TaxField.MARRIED: True, TaxField.NB_CHILDREN: 1, TaxField.SALARY_1_1AJ: 500,
    })
    result = _calculation_details(simulator)["progressive_tax"]
    assert simulator.state[TaxField.HOUSEHOLD_SHARES] == 2.5
    assert [band["upper_bound"] for band in result["brackets"]] == [250, 500, None]
    assert [band["income"] for band in result["brackets"]] == [250, 200, 0]
    assert result["scale_tax"] == 20


def test_empty_income_has_no_negative_chart_values():
    details = _calculation_details(TaxSimulator(2025, {}))
    assert details["progressive_tax"]["taxable_income"] == 0
    assert all(band["income"] == 0 for band in details["progressive_tax"]["brackets"])
    assert details["donation_buckets"][1]["limit"] == 0
    assert details["fiscal_advantages"]["used"] == 0


def test_donations_without_taxable_income_have_no_66_percent_capacity():
    simulator = TaxSimulator(2025, {
        TaxField.CHARITY_DONATION_7UD: 1500, TaxField.CHARITY_DONATION_7UF: 100,
    })
    details = _calculation_details(simulator)
    second = details["donation_buckets"][1]
    assert second["donated"] == 600
    assert second["eligible"] == second["limit"] == second["reduction"] == 0
    assert second["overflow"] == 600
    assert details["fiscal_advantages"]["used"] == 0


def test_donation_overflow_and_limits_match_simulator_without_using_global_ceiling():
    simulator = TaxSimulator(2025, {
        TaxField.SALARY_1_1AJ: 20000,
        TaxField.CHARITY_DONATION_7UD: 2000,
        TaxField.CHARITY_DONATION_7UF: 20000,
    })
    details = _calculation_details(simulator)
    first, second = details["donation_buckets"]
    assert first == {"rate": 0.75, "donated": 2000, "eligible": 1000, "limit": 1000, "reduction": 750, "overflow": 1000}
    assert second == {"rate": 0.66, "donated": 21000, "eligible": 3600, "limit": 3600, "reduction": 2376, "overflow": 17400}
    assert first["reduction"] + second["reduction"] == simulator.state[TaxField.CHARITY_REDUCTION]
    assert details["fiscal_advantages"] == {"limit": 10000, "used": 0, "excess": 0}


def test_donation_details_preserve_simulator_rounding():
    simulator = TaxSimulator(2025, {
        TaxField.SALARY_1_1AJ: 60000, TaxField.CHARITY_DONATION_7UF: 100.5,
    })
    second = _calculation_details(simulator)["donation_buckets"][1]
    assert second["eligible"] == 101
    assert second["reduction"] == pytest.approx(simulator.state[TaxField.CHARITY_REDUCTION])


def test_global_advantage_usage_is_capped_and_excludes_donations():
    simulator = TaxSimulator(2025, {
        TaxField.SALARY_1_1AJ: 200000,
        TaxField.CHARITY_DONATION_7UF: 1000,
        TaxField.SME_CAPITAL_SUBSCRIPTION_7CF: 50000,
        TaxField.HOME_SERVICES_7DB: 10000,
    })
    assert _calculation_details(simulator)["fiscal_advantages"] == {
        "limit": 10000, "used": 10000, "excess": 4000,
    }


@pytest.mark.parametrize("group", ["income", "donation", "investment"])
def test_disabled_groups_are_excluded_but_preserved(app, tax_return, group):
    client = app.test_client()
    endpoint = f"/api/tax-returns/{tax_return.id}/estimation"
    enabled = client.get(endpoint).get_json()
    flag = f"has_{group}_statements"
    assert client.put(f"/api/tax-returns/{tax_return.id}", json={flag: False}).status_code == 200
    excluded = client.get(endpoint).get_json()
    relationship = "ifu_statements" if group == "investment" else f"{group}_statements"
    saved = list(getattr(tax_return, relationship))
    assert len(saved) == 1
    assert excluded != enabled
    # Removing the hidden records produces the same estimate as disabling their group.
    setattr(tax_return, flag, True)
    getattr(tax_return, relationship).clear()
    db.session.commit()
    assert client.get(endpoint).get_json() == excluded


@pytest.mark.parametrize(
    ("resource", "payload"),
    [
        ("income", {"taxpayer_role": "taxpayer1", "employer_name": "Employer", "known_employment_income": 70000}),
        ("donation", {"name": "Charity", "donation_type": "public_interest", "amount": 200}),
        ("ifu", {"title": "Bank", "box_2tr": "2000", "box_2bh": "100", "box_2ck": "50"}),
    ],
)
def test_estimate_changes_after_statement_crud(app, tax_return, resource, payload):
    client = app.test_client()
    endpoint = f"/api/tax-returns/{tax_return.id}/estimation"
    baseline = client.get(endpoint).get_json()
    statement = getattr(tax_return, f"{resource}_statements")[0]
    statement_url = f"/api/{resource}-statements/{statement.id}"
    assert client.put(statement_url, json=payload).status_code == 200
    edited = client.get(endpoint).get_json()
    assert edited != baseline
    assert client.delete(statement_url).status_code == 200
    deleted = client.get(endpoint).get_json()
    assert deleted != edited
    created = client.post(f"/api/tax-returns/{tax_return.id}/{resource}-statements", json=payload)
    assert created.status_code == 201
    assert client.get(endpoint).get_json() == edited


@pytest.mark.parametrize("condition", ["missing", "return_archived", "family_archived", "unsupported_year"])
def test_estimation_errors_do_not_invoke_simulator(app, tax_return, monkeypatch, condition):
    def unexpected_simulation(*args, **kwargs):
        pytest.fail("Unavailable returns must not invoke the simulator")

    monkeypatch.setattr(tax_service, "TaxSimulator", unexpected_simulation)
    return_id = tax_return.id
    status = 410
    if condition == "missing":
        return_id += 1000
        status = 404
    elif condition == "return_archived":
        tax_return.is_archived = True
    elif condition == "family_archived":
        tax_return.family.is_archived = True
    else:
        tax_return.year = 2099
        status = 422
    db.session.commit()

    response = app.test_client().get(f"/api/tax-returns/{return_id}/estimation")
    assert response.status_code == status
    assert set(response.get_json()) == {"error"}
    assert response.get_json()["error"]
    if condition == "unsupported_year":
        assert "2099" in response.get_json()["error"]
