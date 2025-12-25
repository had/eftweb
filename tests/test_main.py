import pytest
from flask import url_for

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
