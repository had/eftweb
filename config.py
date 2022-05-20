import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    BOOTSTRAP_BOOTSWATCH_THEME = 'litera'
    SECRET_KEY = 't0p.5ecr3t'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @staticmethod
    def init_app(app): pass

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(basedir, "eftdb-dev.sqlite")

class TestingConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(basedir, "eftdb-test.sqlite")

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    # TODO
    # 'production': ProductionConfig,
    'default': DevelopmentConfig
}