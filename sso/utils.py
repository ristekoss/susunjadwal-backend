import os
import json

from sso.cas import CASClient
from flask import current_app as app


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
