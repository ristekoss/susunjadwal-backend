import logging
import os

from flask import Flask
from flask_cors import CORS
from flask_mongoengine import MongoEngine
import json
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from dotenv import load_dotenv

from app.message_queue import init_pika
from app.services.scrapper.schedule_scrapper import ScheduleScrapperServices
from app.views.auth import router_auth
from app.views.main import router_main
from app.cron import cron
from uploader.views import router_uploader

from pathlib import Path

load_dotenv()

base_dir = Path(__file__).resolve().parent.parent

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN", ""),
    integrations=[FlaskIntegration()],
    traces_sample_rate=0.5,
)

app = Flask(__name__, instance_relative_config=True)

# config vars
app.config["BASE_PATH"] = "/susunjadwal/api"
app.config["SSO_UI_URL"] = "https://sso.ui.ac.id/cas2/"
app.config["SECRET_KEY"] = "password"
app.config["ACTIVE_PERIOD"] = "2018-2"
app.config["SSO_UI_FORCE_HTTPS"] = False
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
app.config["BASE_DIR"] = base_dir
app.config["FLASK_PIKA_PARAMS"] = {
    "host": os.environ.get("RABBIT_HOST"),
    "username": os.environ.get("RABBIT_USERNAME"),
    "password": os.environ.get("RABBIT_PASSWORD"),
    "port": int(os.environ.get("RABBIT_PORT", "5672"))
}
app.config["FLASK_PIKA_POOL_PARAMS"] = {
    "pool_size": 8,
    'pool_recycle': 10
}

with open(base_dir / "sso" / "faculty-base-additional-info.json") as f:
    app.config["FACULTY_KD_ORG"] = json.load(f)

with open(base_dir / "sso" / "additional-info.json") as f:
    app.config["BASE_KD_ORG"] = json.load(f)

with open(base_dir / "sso" / "faculty_exchange_route.json") as f:
    app.config["FACULTY_EXCHANGE_ROUTE"] = json.load(f)

# uploader
app.config['UPLOAD_FOLDER'] = "__files__"

# Activate gunicorn logger when the application is executed using gunicorn
if __name__ != "__main__" and os.environ.get("FLASK_ENV") != "development":
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

app.config.from_pyfile("config.cfg")
app.register_blueprint(router_auth, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(router_main, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(router_uploader, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(cron)

CORS(app)
MongoEngine(app)


# Init connection to rabbit mq
init_pika(app)

# Init consumer and create exchange
ScheduleScrapperServices.init_service(app)

