from functools import wraps
from flask import Flask
from flask_cors import CORS
from flask_mongoengine import MongoEngine

from app.views.auth import router_auth
from app.views.main import router_main
from app.cron import cron
from uploader.views import router_uploader


app = Flask(__name__, instance_relative_config=True)

# config vars
app.config["BASE_PATH"] = "/susunjadwal/api"
app.config["SSO_UI_URL"] = "https://sso.ui.ac.id/cas2/"
app.config["SECRET_KEY"] = "password"
app.config["ACTIVE_PERIOD"] = "2018-2"
app.config["SSO_UI_FORCE_HTTPS"] = False
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

# uploader
app.config['UPLOAD_FOLDER'] = "__files__"

app.config.from_pyfile("config.cfg")
app.register_blueprint(router_auth, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(router_main, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(router_uploader, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(cron)

CORS(app)
MongoEngine(app)
