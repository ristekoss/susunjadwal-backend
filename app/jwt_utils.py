import datetime
import functools
import jwt
from flask import current_app as app, request, jsonify


EXPIRY_TIME = datetime.datetime.now() + datetime.timedelta(days=365)


def generate_token(user_id, major_id):
    token = jwt.encode({
        'exp': EXPIRY_TIME,
        'user_id': str(user_id),
        'major_id': str(major_id),
    }, app.config["SECRET_KEY"], algorithm='HS256')

    return token.decode()


def extract_data(header):
    try:
        header_type, value = header['Authorization'].split()
        data = jwt.decode(value, app.config["SECRET_KEY"], algorithm='HS256')
    except:
        return None

    return data


def require_jwt_token(func):
    @functools.wraps(func)
    def decorated_func(*args, **kwargs):
        data = extract_data(request.headers)
        if data is None:
            return (jsonify({
                'message': 'There is no token/token is not valid'
            }), 401)
        return func(*args, **kwargs)
    return decorated_func
