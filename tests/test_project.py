import pytest
from app import create_app, db
from flask import url_for

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

