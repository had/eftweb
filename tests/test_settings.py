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
    assert client.get("/api/settings").get_json() == {"theme": "sage-slate"}
    assert not settings_file.exists()

    response = client.put("/api/settings", json={"theme": "mist-blue"})
    assert response.status_code == 200
    assert response.get_json() == {"theme": "mist-blue"}
    assert json.loads(settings_file.read_text(encoding="utf-8")) == {"theme": "mist-blue"}

    restarted_app = create_app("testing")
    restarted_app.config["SETTINGS_FILE"] = str(settings_file)
    assert restarted_app.test_client().get("/api/settings").get_json() == {"theme": "mist-blue"}

    response = client.put("/api/settings", json={"theme": "warm-stone"})
    assert response.status_code == 200
    assert client.get("/api/settings").get_json() == {"theme": "warm-stone"}


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
    assert client.get("/api/settings").get_json() == {"theme": "mist-blue"}
    assert list(tmp_path.glob(".settings-*")) == []
