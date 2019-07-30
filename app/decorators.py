import functools
from flask import jsonify, request

from app.utils import extract_header_data


def require_same_user_id(func):
    @functools.wraps(func)
    def decorated_func(*args, **kwargs):
        data = extract_header_data(request.headers)
        if(data['user_id'] == kwargs['user_id']):
            return func(*args, **kwargs)
        return jsonify({
            'message': 'Unauthorized. Only the resource owner can access this endpoint'
        }), 401
    return decorated_func


def require_jwt_token(func):
    @functools.wraps(func)
    def decorated_func(*args, **kwargs):
        data = extract_header_data(request.headers)
        if data is None:
            return (jsonify({
                'message': 'There is no token/token is not valid'
            }), 401)
        return func(*args, **kwargs)
    return decorated_func
