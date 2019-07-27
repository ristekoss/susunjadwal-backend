import os
import json

from cas import CASClient
from flask import current_app as app

from app.jwt_utils import generate_token
from models.major import Major
from models.period import Period
from models.user import User
from scraper.main import scrape_courses


def get_cas_client(service_url=None, request=None):
    server_url = f"{app.config['SSO_UI_URL']}"
    if server_url and request and server_url.startswith("/"):
        scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
        server_url = scheme + "://" + request.headers["HTTP_HOST"] + server_url

    return CASClient(service_url=service_url, server_url=server_url, version=2)


def authenticate(ticket, client):
    username, attributes, _ = client.verify_ticket(ticket)

    if not username:
        return None

    if "kd_org" in attributes:
        attributes.update(get_additional_info(attributes["kd_org"]) or {})

    sso_profile = {"username": username, "attributes": attributes}
    return sso_profile


def get_additional_info(kd_org):
    path = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(path, "additional-info.json")

    with open(filename, "r") as fd:
        as_json = json.load(fd)
        if kd_org in as_json:
            return as_json[kd_org]

    return None


def process_sso_profile(sso_profile):
    period_name = app.config["ACTIVE_PERIOD"]

    user_npm = sso_profile["attributes"]["npm"]
    major_name = sso_profile["attributes"]["study_program"]
    major_kd_org = sso_profile["attributes"]["kd_org"]

    major = Major.objects(kd_org=major_kd_org).first()
    if major is None:
        major = Major(name=major_name, kd_org=major_kd_org)
        major.save()

    period_detail = Period.objects(
        major_id=major.id, name=period_name, is_detail=True).first()
    period_not_detail = Period.objects(
        major_id=major.id, name=period_name, is_detail=False).first()

    if period_detail is None:
        if period_not_detail is None:
            courses, is_detail = scrape_courses(major_kd_org, period_name)

            if not courses:
                result = {
                    "err": True,
                    "major_name": major_name
                }
                return result
        else:
            courses, is_detail = scrape_courses(
                major_kd_org, period_name, skip_not_detail=True)

        if courses:
            period = Period(
                major_id=major.id,
                name=period_name,
                courses=courses,
                is_detail=is_detail
            )
            period.save()

    user = User.objects(npm=user_npm).first()
    if user is None:
        user = User(
            name=sso_profile["attributes"]["ldap_cn"],
            username=sso_profile["username"],
            npm=user_npm,
            batch=f"20{user_npm[:2]}",
            major=major,
        )
        user.save()

    token = generate_token(user.id, user.major.id)
    result = {
        "user_id": str(user.id),
        "major_id": str(user.major.id),
        "token": token
    }

    return result
