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
from app.views.review import router_review
from app.cron import cron
from uploader.views import router_uploader

from pathlib import Path

load_dotenv(override=True)

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

# Get "instance" configuration from env
app.config.from_mapping(
    SECRET_KEY=os.environ.get("SECRET_KEY"),
    ACTIVE_PERIOD=os.environ.get("ACTIVE_PERIOD"),
    SSO_UI_FORCE_HTTPS=True if os.environ.get("SSO_UI_FORCE_HTTPS").lower() == "true" else False,
    MONGODB_DB=os.environ.get("MONGODB_DB"),
    MONGODB_HOST=os.environ.get("MONGODB_HOST"),
    MONGODB_PORT=int(os.environ.get("MONGODB_PORT")),
    MONGODB_USERNAME=os.environ.get("MONGODB_USERNAME"),
    MONGODB_PASSWORD=os.environ.get("MONGODB_PASSWORD"),
    UPDATE_COURSE_LIST_EXCHANGE_NAME=os.environ.get("UPDATE_COURSE_LIST_EXCHANGE_NAME"),
    SENTRY_DSN=os.environ.get("SENTRY_DSN"),
)

app.register_blueprint(router_auth, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(router_main, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(router_uploader, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(router_review, url_prefix=app.config["BASE_PATH"])
app.register_blueprint(cron)

CORS(app)
MongoEngine(app)

# Init connection to rabbit mq
init_pika(app)

# Init consumer and create exchange
ScheduleScrapperServices.init_service(app)

