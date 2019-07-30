import jwt
from flask import current_app as app


def encode_token(data):
    return jwt.encode(data, app.config["SECRET_KEY"], algorithm='HS256').decode()


def decode_token(token):
    try:
        data = jwt.decode(token, app.config["SECRET_KEY"], algorithm='HS256')
    except:
        return None

    return data
