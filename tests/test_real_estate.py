from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from flask_migrate import downgrade, upgrade
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import create_app, db
from app.family.models import Family, RealEstateProperty
from config import TestingConfig


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def family_endpoint():
    family = Family()
    db.session.add(family)
    db.session.commit()
    return f"/api/families/{family.id}/properties"


def payload(**changes):
    return {
        "name": " Paris apartment ",
        "estimated_value": "350000.25",
        "is_principal_home": False,
        **changes,
    }


def test_properties_persist_edit_and_delete_permanently(app):
    client = app.test_client()
    endpoint = family_endpoint()
    assert client.get(endpoint).get_json() == []
    created = client.post(endpoint, json=payload(is_principal_home=True))
    assert created.status_code == 201
    item = created.get_json()
    assert item["name"] == "Paris apartment"
    assert item["estimated_value"] == "350000.25"
    assert item["is_principal_home"] is True
    db.session.expire_all()
    saved = db.session.get(RealEstateProperty, item["id"])
    assert saved.estimated_value == Decimal("350000.25")
    assert saved.family.properties == [saved]
    target = f"{endpoint}/{item['id']}"
    changed = client.put(target, json=payload(name="Renamed", estimated_value="0"))
    assert changed.status_code == 200
    assert changed.get_json()["estimated_value"] == "0.00"
    assert changed.get_json()["is_principal_home"] is False
    assert client.get(endpoint).get_json() == [changed.get_json()]
    assert client.delete(target).status_code == 204
    assert client.get(endpoint).get_json() == []
    assert db.session.get(RealEstateProperty, item["id"]) is None
    assert client.delete(target).status_code == 404


@pytest.mark.parametrize("editing", [False, True])
def test_principal_home_replacement_requires_confirmation_of_current_property(app, editing):
    client = app.test_client()
    endpoint = family_endpoint()
    previous = client.post(endpoint, json=payload(is_principal_home=True)).get_json()
    if editing:
        new = client.post(endpoint, json=payload(name="Lyon house")).get_json()
        target, save = f"{endpoint}/{new['id']}", client.put
    else:
        target, save = endpoint, client.post
    replacement = payload(name="Lyon house", is_principal_home=True)
    conflict = save(target, json=replacement)
    assert conflict.status_code == 409
    assert conflict.get_json()["principal_home"] == previous
    # A stale confirmation must never clear a different principal home.
    assert save(target, json={**replacement, "replace_principal_home_id": 999}).status_code == 409
    assert client.get(endpoint).get_json()[-1]["is_principal_home"] is True
    result = save(target, json={**replacement, "replace_principal_home_id": previous["id"]})
    assert result.status_code == (200 if editing else 201)
    homes = [item for item in client.get(endpoint).get_json() if item["is_principal_home"]]
    assert homes == [result.get_json()]
    # Editing the principal home itself needs no replacement confirmation.
    assert client.put(f"{endpoint}/{homes[0]['id']}", json=replacement).status_code == 200


@pytest.mark.parametrize(
    "change",
    [
        {"name": " "},
        {"name": 42},
        {"name": "x" * 257},
        {"estimated_value": None},
        {"estimated_value": ""},
        {"estimated_value": True},
        {"estimated_value": -1},
        {"estimated_value": "1.001"},
        {"estimated_value": "NaN"},
        {"estimated_value": "Infinity"},
        {"estimated_value": "1000000000000"},
        {"is_principal_home": "true"},
        {"is_principal_home": 1},
        {"replace_principal_home_id": True},
        {"replace_principal_home_id": "1"},
    ],
)
def test_invalid_properties_cannot_change_saved_data(app, change):
    client = app.test_client()
    endpoint = family_endpoint()
    saved = client.post(endpoint, json=payload()).get_json()
    assert client.post(endpoint, json=payload(**change)).status_code == 400
    assert client.put(f"{endpoint}/{saved['id']}", json=payload(**change)).status_code == 400
    assert client.get(endpoint).get_json() == [saved]


@pytest.mark.parametrize("data", [None, [], "property", {}, {"name": "House"}])
def test_missing_or_invalid_payloads(app, data):
    assert app.test_client().post(family_endpoint(), json=data).status_code == 400


def test_families_are_isolated_and_archived_or_missing_families_are_rejected(app):
    client = app.test_client()
    endpoint, other = family_endpoint(), family_endpoint()
    first = client.post(endpoint, json=payload(is_principal_home=True)).get_json()
    second = client.post(other, json=payload(is_principal_home=True)).get_json()
    assert client.get(endpoint).get_json() == [first]
    assert client.get(other).get_json() == [second]
    for method in (client.put, client.delete):
        assert method(f"{other}/{first['id']}", json=payload()).status_code == 404
        assert method("/api/families/999/properties/999", json=payload()).status_code == 404
    assert client.get("/api/families/999/properties").status_code == 404
    assert client.post("/api/families/999/properties", json=payload()).status_code == 404
    client.delete(endpoint.removesuffix("/properties"))
    assert client.get(endpoint).status_code == 410
    assert client.post(endpoint, json=payload()).status_code == 410
    assert client.put(f"{endpoint}/{first['id']}", json=payload()).status_code == 410
    assert client.delete(f"{endpoint}/{first['id']}").status_code == 410
    assert db.session.get(RealEstateProperty, first["id"]).is_principal_home is True


def test_failed_replacement_rolls_back_both_changes_and_can_be_retried(app, monkeypatch):
    client = app.test_client()
    endpoint = family_endpoint()
    previous = client.post(endpoint, json=payload(is_principal_home=True)).get_json()
    replacement = payload(
        name="Lyon house", is_principal_home=True, replace_principal_home_id=previous["id"]
    )
    with monkeypatch.context() as patch:

        def fail_commit():
            raise SQLAlchemyError("Database unavailable")

        patch.setattr(db.session, "commit", fail_commit)
        assert client.post(endpoint, json=replacement).status_code == 500
    assert client.get(endpoint).get_json() == [previous]
    assert client.post(endpoint, json=replacement).status_code == 201


def test_database_prevents_multiple_principal_homes_and_cascades_family_deletion(app):
    family_endpoint()
    family = Family.query.one()
    family.properties.append(
        RealEstateProperty(name="First", estimated_value=1, is_principal_home=True)
    )
    db.session.commit()
    family.properties.append(
        RealEstateProperty(name="Second", estimated_value=1, is_principal_home=True)
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert len(family.properties) == 1
    db.session.delete(family)
    db.session.commit()
    assert RealEstateProperty.query.count() == 0


def test_real_estate_migration_upgrades_and_downgrades(tmp_path, monkeypatch):
    monkeypatch.setattr(
        TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'properties.sqlite'}"
    )
    app = create_app("testing")
    directory = str(Path(__file__).resolve().parents[1] / "migrations")
    # Alembic's logging configuration disables existing loggers; restore Flask's
    # logger after this test so later API tests still capture application errors.
    monkeypatch.setattr(app.logger, "disabled", app.logger.disabled)
    with app.app_context():
        upgrade(directory=directory, revision="ef2a91c7d430")
        with db.engine.begin() as connection:
            connection.execute(sa.text("INSERT INTO families (id) VALUES (1)"))
        upgrade(directory=directory, revision="a4d71b8e902c")
        with db.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO real_estate_properties (family_id, name, estimated_value) VALUES (1, 'House', 123456.78)"
                )
            )
            assert (
                connection.execute(
                    sa.text("SELECT is_principal_home FROM real_estate_properties")
                ).scalar_one()
                == 0
            )
            connection.execute(sa.text("UPDATE real_estate_properties SET is_principal_home = 1"))
        with pytest.raises(IntegrityError), db.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO real_estate_properties (family_id, name, estimated_value, is_principal_home) VALUES (1, 'Other', 1, 1)"
                )
            )
        downgrade(directory=directory, revision="ef2a91c7d430")
        assert "real_estate_properties" not in sa.inspect(db.engine).get_table_names()
        with db.engine.connect() as connection:
            assert connection.execute(sa.text("SELECT id FROM families")).scalar_one() == 1
        upgrade(directory=directory, revision="a4d71b8e902c")
        db.session.remove()
        db.engine.dispose()
