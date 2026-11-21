import datetime
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_bootstrap import Bootstrap4
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup

from app.service.tax_parameters import load_tax_parameters
from config import config

db = SQLAlchemy()
bootstrap = Bootstrap4()
migrate = Migrate()


def fontawesome_html():
    return Markup(
        '<link rel="stylesheet" '
        'href="https://use.fontawesome.com/releases/v5.14.0/css/all.css" '
        'crossorigin="anonymous">'
    )

class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, datetime.date):
            return obj.strftime('%Y-%m-%d')
        return super().default(obj)


def load_environment(dotenv_path=None):
    load_dotenv(dotenv_path or Path(__file__).resolve().parent.parent / ".env", override=False)


def create_app(config_name):
    load_environment()
    app = Flask(__name__)
    app.json_provider_class = CustomJSONProvider
    app.json = app.json_provider_class(app)

    app.config.from_object(config[config_name])
    app.config.setdefault("SETTINGS_FILE", str(Path(app.instance_path) / "settings.json"))
    app.config.setdefault(
        "TAX_PARAMETERS_FILE",
        os.environ.get("TAX_PARAMETERS_FILE", str(Path(app.root_path) / "tax_parameters.toml")),
    )
    load_tax_parameters(app.config["TAX_PARAMETERS_FILE"])

    bootstrap.init_app(app)
    app.jinja_env.globals["fontawesome_html"] = fontawesome_html
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)

    from .family import models as family_models  # noqa: F401
    from .main import main as main_bp
    app.register_blueprint(main_bp)
    from .stocks import stocks as stocks_bp
    app.register_blueprint(stocks_bp)
    from .tax import tax as tax_bp
    from .tax import views as tax_views  # noqa: F401
    app.register_blueprint(tax_bp)
    from .api import api as api_bp
    app.register_blueprint(api_bp)

    return app
