import jwt
from flask import current_app as app


def encode_token(data):
    return jwt.encode(data, app.config["SECRET_KEY"], algorithm='HS256')


def decode_token(token):
    try:
        data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=['HS256'])
    except Exception as e:
        return None

    return data
