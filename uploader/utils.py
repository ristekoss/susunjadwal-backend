import functools
from flask import (
    redirect,
    request,
    url_for
)

from app.jwt_utils import decode_token, encode_token
from sso.utils import get_cas_client


def get_sso_login_url():
    service_url = url_for("router_uploader.auth", _external=True)
    client = get_cas_client(service_url=service_url)
    login_url = client.get_login_url()
    return login_url


def get_sso_logout_url():
    redirect_url = url_for("router_uploader.login", _external=True)
    client = get_cas_client()
    logout_url = client.get_logout_url(redirect_url=redirect_url)

    return logout_url


def generate_token(sso_profile):
    token = encode_token({
        "username": sso_profile["username"],
        "npm": sso_profile["attributes"]["npm"],
        "study_program": sso_profile["attributes"]["study_program"],
        "educational_program": sso_profile["attributes"]["educational_program"]
    })
    return token


def require_jwt_cookie(func):
    @functools.wraps(func)
    def decorated_func(*args, **kwargs):
        profile = decode_token(request.cookies.get("__token"))
        if profile is None:
            login_url = get_sso_login_url()
            return redirect(login_url)

        kwargs["profile"] = profile
        return func(*args, **kwargs)

    return decorated_func
