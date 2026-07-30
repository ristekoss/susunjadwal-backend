import json
import datetime

from flask import Blueprint, Response, stream_with_context, request, jsonify, current_app
from app.decorators import require_jwt_token
from app.jwt_utils import decode_token
from models.user import User
from models.major import Major
from models.period import Period
from scraper.main import scrape_courses_with_credentials

router_scraper = Blueprint('router_scraper', __name__)

def _format_sse(data, event=None):
    payload = f"data: {json.dumps(data)}\n"
    if event:
        payload = f"event: {event}\n{payload}"
    return payload + "\n"

@router_scraper.route('/scrape-siak-ng', methods=['POST'])
@require_jwt_token
def scrape_siak_ng():
    header_data = request.headers
    user_data = decode_token(header_data["Authorization"].split()[1])
    user = User.objects(id=user_data['user_id']).first()

    if not user:
        return jsonify({'message': 'User not found.'}), 404

    data = request.get_json()
    if not data:
        return Response("Error: Request body is required.", status=400)

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return Response("Error: Username and password are required.", status=400)

    def generate(user_obj, siak_username, siak_password):
        active_period = current_app.config.get("ACTIVE_PERIOD", None)
        if not active_period:
            yield _format_sse({"type": "error", "message": "No active period configured."}, event='log')
            return

        yield _format_sse({"type": "status", "message": f"Authenticating as {siak_username} on SLCM..."}, event='log')

        try:
            courses = scrape_courses_with_credentials(active_period, siak_username, siak_password)
        except Exception as e:
            yield _format_sse({"type": "error", "message": f"Scraping failed: {str(e)}"}, event='log')
            return

        if not courses:
            yield _format_sse({"type": "error", "message": "No courses returned from scraper."}, event='log')
            return

        yield _format_sse({
            "type": "status",
            "message": f"Scraped {len(courses)} courses. Saving to database..."
        }, event='log')

        try:
            major = Major.objects(kd_org=user_obj.major.kd_org).first()
            if not major:
                major = Major(kd_org=user_obj.major.kd_org, name=f"Major-{user_obj.major.kd_org}")
                major.save()

            period = Period.objects(
                major_id=major.id,
                name=active_period,
                is_detail=True
            ).first()

            if period:
                period.courses = []
                period.save()
                yield _format_sse({"type": "status", "message": "Updated existing period."}, event='log')
            else:
                period = Period(
                    major_id=major.id,
                    name=active_period,
                    courses=[],
                    is_detail=True
                )
                period.save()
                yield _format_sse({"type": "status", "message": "Created new period."}, event='log')

            for course in courses:
                course.classes = [cl for cl in course.classes if cl.schedule_items]
            period.courses = courses
            period.last_update_at = datetime.datetime.now(datetime.timezone.utc)
            period.save()

            yield _format_sse({
                "type": "success",
                "message": f"Successfully saved {len(courses)} courses to database."
            }, event='log')

        except Exception as e:
            yield _format_sse({"type": "error", "message": f"Database error: {str(e)}"}, event='log')

    return Response(
        stream_with_context(generate(user, username, password)),
        content_type='text/event-stream'
    )


@router_scraper.route('/scrape-siak-ng/status', methods=['GET'])
def scraper_status():
    return jsonify({"message": "Scraper service is running", "version": "2.0"}), 200
