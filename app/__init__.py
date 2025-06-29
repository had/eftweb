import datetime
from flask import Flask
from flask_bootstrap import Bootstrap4
from flask_fontawesome import FontAwesome
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import config
from flask.json import JSONEncoder
from flask_cors import CORS

db = SQLAlchemy()
bootstrap = Bootstrap4()
fa = FontAwesome()
migrate = Migrate()

class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.date):
            return obj.strftime('%Y-%m-%d')
        return super().default(obj)


def create_app(config_name):
    app = Flask(__name__)
    # CORS(app)
    # CORS(app, origins=["http://localhost:5173"], supports_credentials=True)
    app.json_encoder = CustomJSONEncoder

    app.config.from_object(config[config_name])

    bootstrap.init_app(app)
    fa.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)

    from .main import main as main_bp
    app.register_blueprint(main_bp)
    from .stocks import stocks as stocks_bp
    app.register_blueprint(stocks_bp)
    from .tax import tax as tax_bp
    app.register_blueprint(tax_bp)
    from .api import api as api_bp
    # CORS(api_bp, resources={r"/*": {"origins": "http://localhost:5173/"}})
    app.register_blueprint(api_bp)

    # CORS(app, resources={r"/*": {"origins": "http://localhost:5173/"}})
    return app

# from routes import *
# from .models import *

