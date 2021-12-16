import os.path

from flask import Flask
from flask_bootstrap import Bootstrap
from flask_fontawesome import FontAwesome
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['BOOTSTRAP_BOOTSWATCH_THEME'] = 'litera'
app.config['SECRET_KEY'] = 't0p.5ecr3t'
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + os.path.join(basedir,"eftdb.sqlite")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

bootstrap = Bootstrap(app)
fa = FontAwesome(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

from routes import *
from models import *