from datetime import date

import pytest
from flask import url_for
from sqlalchemy.exc import IntegrityError

from app import create_app, db
from app.family.models import Family, FamilyMember, IncomeStatement, TaxReturn
from app.main.models import Project


@pytest.fixture()
def app():
    app = create_app("testing")
    app.config.update({
        "SERVER_NAME": "test.org"
    })
    app_context = app.app_context()
    app_context.push()
    db.create_all()
    yield app
    db.drop_all()
    app_context.pop()

def test_index(app):
    client = app.test_client()
    response = client.get(url_for('main.index'))
    assert "Hello Guest" in response.get_data(as_text=True)

def test_project(app):
    client = app.test_client()
    import time
    now = time.time()

    # create
    response_create = client.post(url_for('main.index'), data={
        'name': f"Unit-test project {now}",
        'situation': "Married",
        "nb_children": "3"
    })
    assert response_create.status_code == 302

    # check
    response_project = client.get(url_for('main.project_tax', project_id=1))
    response_project_data = response_project.get_data(as_text=True)
    assert f"Project Unit-test project {now}" in response_project_data
    assert "Married = Yes ; Children = 3" in response_project_data

    #update
    response_update = client.post(url_for('main.project_update', project_id=1), data={
        'name': "Unit-test project update",
        'situation': "Single",
        "nb_children": "2"
    })
    assert response_update.status_code == 302
    response_project_2 = client.get(url_for('main.project_tax', project_id=1))
    response_project_2_data = response_project_2.get_data(as_text=True)
    assert "Project Unit-test project update" in response_project_2_data
    assert "Married = No ; Children = 2" in response_project_2_data

    # delete (+ redirect to /)
    response_delete = client.get(url_for('main.project_delete', project_id=1))
    assert response_delete.status_code == 302
    assert '<a href="/">/</a>' in response_delete.get_data(as_text=True)
    response_index = client.get(url_for('main.index'))
    assert "Unit-test" not in response_index.get_data(as_text=True)


def test_tax_statement_api(app):
    project = Project(name="Tax return API family", married=False, nb_children=0)
    db.session.add(project)
    db.session.commit()
    client = app.test_client()
    endpoint = f"/api/projects/{project.id}/tax-statements"

    assert client.get(endpoint).get_json() == []

    missing_year = client.post(endpoint, json={})
    assert missing_year.status_code == 400

    invalid_year = client.post(endpoint, json={"year": "2026"})
    assert invalid_year.status_code == 400

    created = client.post(endpoint, json={"year": 2026})
    assert created.status_code == 201
    assert created.get_json()["year"] == 2026

    listed = client.get(endpoint)
    assert listed.status_code == 200
    assert listed.get_json() == [created.get_json()]

    duplicate = client.post(endpoint, json={"year": 2026})
    assert duplicate.status_code == 409


def test_family_members_use_unique_taxpayer_and_child_slots(app):
    family = Family()
    db.session.add(family)
    db.session.commit()

    member = FamilyMember(
        family_id=family.id,
        first_name="Ada",
        last_name="Lovelace",
        date_of_birth=date(1815, 12, 10),
        role="taxpayer1",
        position=1,
    )
    db.session.add(member)
    db.session.commit()

    assert family.taxpayer1 == member
    assert family.taxpayer2 is None
    assert family.children == []

    duplicate_taxpayer = FamilyMember(
        family_id=family.id,
        first_name="Grace",
        last_name="Hopper",
        date_of_birth=date(1906, 12, 9),
        role="taxpayer1",
        position=1,
    )
    db.session.add(duplicate_taxpayer)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    seventh_child = FamilyMember(
        family_id=family.id,
        first_name="Katherine",
        last_name="Johnson",
        date_of_birth=date(1918, 8, 26),
        role="child",
        position=7,
    )
    db.session.add(seventh_child)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def family_payload(**overrides):
    payload = {
        "taxpayer1": {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": "1815-12-10",
        },
        "taxpayer2": None,
        "children": [],
    }
    payload.update(overrides)
    return payload


def test_family_api_creates_updates_lists_and_archives_families(app):
    client = app.test_client()

    missing_taxpayer = client.post("/api/families", json={})
    assert missing_taxpayer.status_code == 400

    incomplete_taxpayer2 = client.post(
        "/api/families", json=family_payload(taxpayer2={"first_name": "William"})
    )
    assert incomplete_taxpayer2.status_code == 400

    too_many_children = client.post(
        "/api/families",
        json=family_payload(children=[family_payload()["taxpayer1"] for _ in range(7)]),
    )
    assert too_many_children.status_code == 400

    created = client.post("/api/families", json=family_payload())
    assert created.status_code == 201
    family = created.get_json()
    assert family["taxpayer1"]["first_name"] == "Ada"

    updated = client.put(
        f"/api/families/{family['id']}",
        json=family_payload(
            taxpayer2={
                "first_name": "William",
                "last_name": "King-Noel",
                "date_of_birth": "1794-02-26",
            },
            children=[
                {
                    "first_name": "Byron",
                    "last_name": "Lovelace",
                    "date_of_birth": "1836-05-12",
                }
            ],
        ),
    )
    assert updated.status_code == 200
    assert len(updated.get_json()["children"]) == 1

    assert client.get("/api/families").get_json()[0]["id"] == family["id"]
    archived = client.delete(f"/api/families/{family['id']}")
    assert archived.status_code == 200
    assert client.get("/api/families").get_json() == []
    assert client.get("/api/families?archived=true").get_json()[0]["id"] == family["id"]
    assert client.put(f"/api/families/{family['id']}", json=family_payload()).status_code == 410


def test_family_tax_returns_are_unique_and_unavailable_when_archived(app):
    client = app.test_client()
    family = client.post("/api/families", json=family_payload()).get_json()
    endpoint = f"/api/families/{family['id']}/tax-returns"

    assert client.get(endpoint).get_json() == []
    assert client.post(endpoint, json={}).status_code == 400

    created = client.post(
        endpoint,
        json={
            "year": 2026,
            "has_income_statements": True,
            "has_investment_statements": True,
        },
    )
    assert created.status_code == 201
    assert created.get_json()["year"] == 2026
    assert created.get_json()["has_income_statements"] is True
    assert created.get_json()["has_donation_statements"] is False
    assert created.get_json()["has_investment_statements"] is True
    assert client.post(endpoint, json={"year": 2026}).status_code == 409
    assert client.get(endpoint).get_json() == [created.get_json()]

    updated = client.put(
        f"/api/tax-returns/{created.get_json()['id']}",
        json={"year": 2027, "has_income_statements": False, "has_donation_statements": True},
    )
    assert updated.status_code == 200
    assert updated.get_json()["year"] == 2026
    assert updated.get_json()["has_income_statements"] is False
    assert updated.get_json()["has_donation_statements"] is True

    archived = client.delete(f"/api/tax-returns/{created.get_json()['id']}")
    assert archived.status_code == 200
    assert client.get(endpoint).get_json() == []
    assert client.get(f"{endpoint}?archived=true").get_json()[0]["id"] == created.get_json()["id"]
    assert client.put(f"/api/tax-returns/{created.get_json()['id']}", json={}).status_code == 410
    assert client.delete(f"/api/tax-returns/{created.get_json()['id']}").status_code == 410

    client.delete(f"/api/families/{family['id']}")
    assert client.get(endpoint).status_code == 410
    assert client.post(endpoint, json={"year": 2027}).status_code == 410


def test_income_statements_allow_multiple_statements_per_taxpayer(app):
    client = app.test_client()
    family = client.post(
        "/api/families",
        json=family_payload(
            taxpayer2={
                "first_name": "Grace",
                "last_name": "Hopper",
                "date_of_birth": "1906-12-09",
            }
        ),
    ).get_json()
    tax_return = client.post(
        f"/api/families/{family['id']}/tax-returns",
        json={"year": 2026, "has_income_statements": True},
    ).get_json()
    endpoint = f"/api/tax-returns/{tax_return['id']}/income-statements"

    assert client.get(endpoint).get_json() == []
    assert client.post(endpoint, json={}).status_code == 400
    assert client.post(
        endpoint,
        json={"taxpayer_role": "taxpayer1", "employer_name": "Google"},
    ).status_code == 400
    assert client.post(
        endpoint,
        json={"taxpayer_role": "child", "employer_name": "Invalid", "known_employment_income": 1},
    ).status_code == 400
    assert client.post(
        endpoint,
        json={
            "taxpayer_role": "taxpayer2",
            "employer_name": "Anthropic",
            "known_employment_income": 1000.25,
        },
    ).status_code == 201
    assert client.post(
        endpoint,
        json={
            "taxpayer_role": "taxpayer1",
            "employer_name": "Google",
            "known_employment_income": 2000,
            "income_tax_withheld": 100,
        },
    ).status_code == 201
    assert client.post(
        endpoint,
        json={
            "taxpayer_role": "taxpayer1",
            "employer_name": "Exxon",
            "supplementary_pension_contributions": 25,
        },
    ).status_code == 201
    statements = client.get(endpoint).get_json()
    assert len(statements) == 3
    assert statements[0]["known_employment_income"] == "1000.25"
    assert statements[1]["income_tax_withheld"] == "100.00"

    replacement = client.put(
        f"/api/families/{family['id']}",
        json=family_payload(
            taxpayer2={
                "first_name": "Katherine",
                "last_name": "Johnson",
                "date_of_birth": "1918-08-26",
            }
        ),
    )
    assert replacement.status_code == 200
    assert [statement["taxpayer_role"] for statement in client.get(endpoint).get_json()] == [
        "taxpayer2",
        "taxpayer1",
        "taxpayer1",
    ]

    client.put(f"/api/tax-returns/{tax_return['id']}", json={"has_income_statements": False})
    assert client.get(endpoint).status_code == 200
    assert client.post(
        endpoint,
        json={"taxpayer_role": "taxpayer1", "employer_name": "Later", "known_employment_income": 1},
    ).status_code == 409

    client.delete(f"/api/tax-returns/{tax_return['id']}")
    assert client.get(endpoint).status_code == 410


def test_income_statement_model_cascades_with_tax_return(app):
    family = Family()
    tax_return = TaxReturn(family=family, year=2026, has_income_statements=True)
    statement = IncomeStatement(
        taxpayer_role="taxpayer1",
        employer_name="Google",
        known_employment_income=100,
    )
    tax_return.income_statements.append(statement)
    db.session.add(tax_return)
    db.session.commit()

    db.session.delete(tax_return)
    db.session.commit()
    assert IncomeStatement.query.count() == 0
