import json

import pytest

from app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app("testing")
    app.config["SETTINGS_FILE"] = str(tmp_path / "settings.json")
    return app.test_client()


def test_default_and_persistence(client, tmp_path):
    settings_file = tmp_path / "settings.json"
    assert client.get("/api/settings").get_json() == {
        "theme": "sage-slate",
        "number_locale": "en-GB",
    }
    assert not settings_file.exists()

    response = client.put("/api/settings", json={"theme": "mist-blue"})
    assert response.status_code == 200
    assert response.get_json() == {"theme": "mist-blue", "number_locale": "en-GB"}
    assert json.loads(settings_file.read_text(encoding="utf-8")) == {
        "theme": "mist-blue",
        "number_locale": "en-GB",
    }

    restarted_app = create_app("testing")
    restarted_app.config["SETTINGS_FILE"] = str(settings_file)
    assert restarted_app.test_client().get("/api/settings").get_json() == {
        "theme": "mist-blue",
        "number_locale": "en-GB",
    }

    response = client.put("/api/settings", json={"theme": "warm-stone"})
    assert response.status_code == 200
    assert client.get("/api/settings").get_json() == {
        "theme": "warm-stone",
        "number_locale": "en-GB",
    }

    response = client.put("/api/settings", json={"theme": "midnight-slate"})
    assert response.status_code == 200
    assert response.get_json() == {"theme": "midnight-slate", "number_locale": "en-GB"}
    assert json.loads(settings_file.read_text(encoding="utf-8")) == {
        "theme": "midnight-slate",
        "number_locale": "en-GB",
    }
    assert restarted_app.test_client().get("/api/settings").get_json() == {
        "theme": "midnight-slate",
        "number_locale": "en-GB",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"theme": "yellow"},
        {"theme": None},
        {"theme": []},
        {"theme": "sage-slate", "extra": True},
        [],
    ],
)
def test_invalid_theme_does_not_write(client, tmp_path, payload):
    response = client.put("/api/settings", json=payload)
    assert response.status_code == 400
    assert not (tmp_path / "settings.json").exists()


def test_failed_write_returns_error_and_keeps_previous_choice(client, tmp_path, monkeypatch):
    client.put("/api/settings", json={"theme": "mist-blue"})

    def fail_replace(source, destination):
        raise OSError("disk is full")

    monkeypatch.setattr("app.settings.os.replace", fail_replace)

    response = client.put("/api/settings", json={"theme": "warm-stone"})
    assert response.status_code == 500
    assert response.get_json() == {"error": "Failed to save settings"}
    assert client.get("/api/settings").get_json() == {
        "theme": "mist-blue",
        "number_locale": "en-GB",
    }
    assert list(tmp_path.glob(".settings-*")) == []


@pytest.mark.parametrize("locale", ["en-GB", "en-US", "fr-FR", "de-DE", "es-ES", "it-IT"])
def test_number_locale_persists_and_theme_updates_preserve_it(client, tmp_path, locale):
    client.put("/api/settings", json={"theme": "midnight-slate"})
    expected = {"theme": "midnight-slate", "number_locale": locale}
    response = client.put("/api/settings", json={"number_locale": locale})
    assert response.status_code == 200
    assert response.get_json() == expected
    assert json.loads((tmp_path / "settings.json").read_text()) == expected

    restarted_app = create_app("testing")
    restarted_app.config["SETTINGS_FILE"] = str(tmp_path / "settings.json")
    assert restarted_app.test_client().get("/api/settings").get_json() == expected

    client.put("/api/settings", json={"theme": "warm-stone"})
    assert client.get("/api/settings").get_json() == {**expected, "theme": "warm-stone"}


def test_both_settings_can_be_updated_together(client):
    expected = {"theme": "mist-blue", "number_locale": "fr-FR"}
    response = client.put("/api/settings", json=expected)
    assert response.status_code == 200
    assert response.get_json() == expected


@pytest.mark.parametrize("locale", [None, [], {}, True, "", "invalid", "fr", "en-gb"])
def test_invalid_number_locale_keeps_previous_settings(client, tmp_path, locale):
    expected = {"theme": "mist-blue", "number_locale": "fr-FR"}
    client.put("/api/settings", json=expected)
    before = (tmp_path / "settings.json").read_bytes()
    response = client.put("/api/settings", json={"theme": "warm-stone", "number_locale": locale})
    assert response.status_code == 400
    assert client.get("/api/settings").get_json() == expected
    assert (tmp_path / "settings.json").read_bytes() == before


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"theme": "mist-blue"}', {"theme": "mist-blue", "number_locale": "en-GB"}),
        (
            '{"theme": "mist-blue", "number_locale": "invalid"}',
            {"theme": "mist-blue", "number_locale": "en-GB"},
        ),
        (
            '{"theme": "invalid", "number_locale": "fr-FR"}',
            {"theme": "sage-slate", "number_locale": "fr-FR"},
        ),
        ("[]", {"theme": "sage-slate", "number_locale": "en-GB"}),
        ("invalid json", {"theme": "sage-slate", "number_locale": "en-GB"}),
    ],
)
def test_existing_and_invalid_settings_fall_back_per_field(client, tmp_path, content, expected):
    (tmp_path / "settings.json").write_text(content)
    assert client.get("/api/settings").get_json() == expected
