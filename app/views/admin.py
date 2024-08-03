import html
from flask import (
    Blueprint,
    jsonify,
    request
)

from datetime import datetime
from app.decorators import require_jwt_token, require_admin_jwt
from app.jwt_utils import decode_token
from models.admin import Admin
from models.review import Review
from app.utils import generate_admin_jwt

router_admin = Blueprint('router_admin', __name__)

@router_admin.route('/admin', methods=['GET'])
@require_jwt_token
@require_admin_jwt
def admin_test():
    return (jsonify({
        "Message": "Admin api accessed."
    }), 200)


@router_admin.route("/admin/login", methods=['POST'])
def admin_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    admin = Admin.objects(username=username).first()

    print(admin)

    if(admin and admin.check_password(password)):
        token = generate_admin_jwt()
        return (jsonify({
            'token': token
        }), 200)

    return (jsonify({
        'message': 'Invalid credentials.'
    }), 401)



@router_admin.route("admin/reviews-overview", methods=['GET'])
@require_jwt_token
@require_admin_jwt
def admin_review_overview():
    total_reviews = Review.objects.count()
    if total_reviews == 0:
        return jsonify({
            'average_rating': 0,
            'rating_counts': {str(i): 0 for i in range(1, 6)}
        }), 200

    total_rating = Review.objects.sum('rating')
    average_rating = total_rating / total_reviews

    rating_counts = {str(i): Review.objects(rating=i).count() for i in range(1, 6)}

    return jsonify({
        'average_rating': average_rating,
        'rating_counts': rating_counts
    }), 200


@router_admin.route("/admin/reviews/list", methods=['GET'])
@require_jwt_token
@require_admin_jwt
def admin_review_list():
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        return (jsonify({
            'message': 'Invalid page number.'
        }), 400)
    
    if page <= 0:
        return (jsonify({
            'message': 'Page must be a positive integer.'
        }), 400)
    
    data = request.json if request.json else {}
    per_page = data.get('per_page', 10)

    try:
        per_page = int(per_page)
        if per_page <= 0:
            raise ValueError
    except ValueError:
        return jsonify({'message': 'per_page must be a positive integer.'}), 400
    
    skip = (page - 1) * per_page

    reviews = Review.objects.order_by('-created_at').skip(skip).limit(per_page)
    total_reviews = Review.objects.count()
    total_pages = (total_reviews + per_page - 1) // per_page 

    serialized_reviews = [review.serialize() for review in reviews]

    return jsonify({
        'page': page,
        'total_page': total_pages,
        'per_page': per_page,
        'total_reviews': total_reviews,
        'reviews': serialized_reviews
    }), 200


@router_admin.route("admin/review/status/<review_id>", methods=['PATCH'])
@require_jwt_token
@require_admin_jwt
def admin_edit_review_status(review_id):
    data = request.json
    new_status = data.get("reviewed")

    if new_status is None:
        return jsonify({'message': 'Missing reviewed status.'}), 400

    try:
        review = Review.objects.get(id=review_id)
    except Review.DoesNotExist:
        return jsonify({'message': 'Review not found.'}), 404

    review.reviewed = new_status
    review.save()

    return jsonify({
        'id': str(review.id),
        'reviewed': review.reviewed
    }), 200


@router_admin.route("/admin/review/delete/<review_id>", methods=['DELETE'])
@require_jwt_token
@require_admin_jwt
def admin_delete_review(review_id):
    try:
        review = Review.objects.get(id=review_id)
    except Review.DoesNotExist:
        return jsonify({'message': 'Review not found.'}), 404

    review.delete()
    return jsonify({'message': 'Review deleted successfully.'}), 200
