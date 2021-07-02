from flask import Flask
from flask_cors import CORS
from flask_mongoengine import MongoEngine
import json

from app.views.auth import router_auth
from app.views.main import router_main
from app.cron import cron
from uploader.views import router_uploader

from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent

app = Flask(__name__, instance_relative_config=True)

# config vars
app.config["BASE_PATH"] = "/susunjadwal/api"
app.config["SSO_UI_URL"] = "https://sso.ui.ac.id/cas2/"
app.config["SECRET_KEY"] = "password"
app.config["ACTIVE_PERIOD"] = "2018-2"
app.config["SSO_UI_FORCE_HTTPS"] = False
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
app.config["BASE_DIR"] = base_dir

with open(base_dir / "sso" / "faculty-base-additional-info.json") as f:
    app.config["FACULTY_KD_ORG"] = json.load(f)

with open(base_dir / "sso" / "additional-info.json") as f:
    app.config["BASE_KD_ORG"] = json.load(f)

# uploader
app.config['UPLOAD_FOLDER'] = "__files__"

app.config.from_pyfile("config.cfg")
app.register_blueprint(router_auth, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(router_main, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(router_uploader, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(cron)

CORS(app)
MongoEngine(app)
