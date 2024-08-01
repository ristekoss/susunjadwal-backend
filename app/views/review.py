import html
from flask import (
    Blueprint,
    jsonify,
    request
)

from datetime import datetime
from app.decorators import require_jwt_token, require_same_user_id
from app.jwt_utils import decode_token
from models.user import User
from models.review import Review
from app.utils import get_user_id, get_app_config

router_review = Blueprint('router_review', __name__)

"""
Basic ping / status check
"""
@router_review.route('/review', methods=['GET'])
def status():
    return (jsonify({
        "message": "review feature is up",
    }), 200)


@router_review.route('/review/<user_id>', methods=['POST'])
@require_jwt_token
@require_same_user_id
def create_review(user_id):
    data = request.json
    rating = data.get('rating')
    comment = data.get('comment')

    if not(1 <= rating <= 5):
        return (jsonify({'message': 'Rating must be between 1 and 5.'}), 400)
    
    user = User.objects(id=user_id).first()
    if not user:
        return (jsonify({'message': 'User not found.'}), 400)
    
    review = Review(
        user=user,
        rating=rating,
        comment=comment
    )
    review.save()

    return (jsonify({
        'message': 'Review saved'
    }), 201)