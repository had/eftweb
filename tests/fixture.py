import pytest
from app import create_app, db

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