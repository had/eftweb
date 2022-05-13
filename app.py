from flask import Flask
from flask_bootstrap import Bootstrap
from flask_fontawesome import FontAwesome
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import config

db = SQLAlchemy()
bootstrap = Bootstrap()
fa = FontAwesome()
migrate = Migrate()

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    bootstrap.init_app(app)
    fa.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    return app

app = create_app("default")

from routes import *
from models import *

