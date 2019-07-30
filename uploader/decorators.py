import functools

from flask import (
    redirect,
    request
)

from app.jwt_utils import decode_token
from uploader.utils import get_sso_login_url


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
