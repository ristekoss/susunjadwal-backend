import functools
from flask import request

from app.jwt_utils import extract_data


def require_same_user_id(func):
    @functools.wraps(func)
    def decorated_func(*args, **kwargs):
        data = extract_data(request.headers)
        if(data['user_id'] == kwargs['user_id']):
            return func(*args, **kwargs)
        return jsonify({
            'message': 'Unauthorized. Only the resource owner can access this endpoint'
        }), 401
    return decorated_func
