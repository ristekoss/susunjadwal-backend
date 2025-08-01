from flask import Blueprint, Response, stream_with_context, request, jsonify
from app.decorators import require_jwt_token
from app.jwt_utils import decode_token
from models.user import User
from models.major import Major
from models.period import Period, Course, Class, ScheduleItem
from scraper.siak_ng_scraper import scrape_siak_ng_courses, format_sse
import json
import re
import datetime

router_scraper = Blueprint('router_scraper', __name__)

@router_scraper.route('/scrape-siak-ng', methods=['POST'])
@require_jwt_token
def scrape_siak_ng():
    """
    New SIAK NG scraper endpoint that integrates with the main backend.
    This endpoint saves scraped courses to the database and provides real-time updates via SSE.
    """
    # Get user data from JWT token
    header_data = request.headers
    user_data = decode_token(header_data["Authorization"].split()[1])
    user: User = User.objects(id=user_data['user_id']).first()
    
    if not user:
        return jsonify({'message': 'User not found.'}), 404
    
    data = request.get_json()
    if not data:
        return Response("Error: Request body is required.", status=400)

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return Response("Error: Username and password are required.", status=400)
    
    def generate_logs_and_save(user_obj, siak_username, siak_password):
        scraper_generator = scrape_siak_ng_courses(siak_username, siak_password)
        courses_data = None
        period_name = None
        target_period = None
        
        for event in scraper_generator:
            # Check if this is the result event with courses data
            if "event: result" in event:
                try:
                    data_line = event.split("data: ")[1]
                    result_data = json.loads(data_line)
                    courses_data = result_data.get('courses')
                    period_name = result_data.get('period_name')
                    target_period = result_data.get('period') 
                except (IndexError, json.JSONDecodeError) as e:
                    yield format_sse({
                        "type": "error", 
                        "message": f"Error parsing scraper result: {str(e)}"
                    }, event='log')
                    pass
            
            yield event
            
        # Save courses to database if we got them
        if courses_data and target_period:
            try:
                yield format_sse({
                    "type": "status", 
                    "message": "Saving courses to database..."
                }, event='log')
                
                major = Major.objects(kd_org=user_obj.major.kd_org).first()
                if not major:
                    major = Major(kd_org=user_obj.major.kd_org, name=f"Major-{user_obj.major.kd_org}")
                    major.save()
                
                period_instance = Period.objects(
                    major_id=major.id,
                    name=target_period,
                    is_detail=True
                ).first()
                
                if period_instance:
                    period_instance.courses = []
                    period_instance.save()
                    yield format_sse({
                        "type": "status", 
                        "message": "Updated existing period with new courses."
                    }, event='log')
                else:
                    period_instance = Period(
                        major_id=major.id,
                        name=target_period,
                        courses=[],
                        is_detail=True
                    )
                    period_instance.save()
                    yield format_sse({
                        "type": "status", 
                        "message": "Created new period for courses."
                    }, event='log')
                
                converted_courses = []
                for course_data in courses_data:
                    try:
                        classes = []
                        for class_data in course_data.get('classes', []):
                            schedule_items = []
                            lecturers = []
                            class_name = class_data.get('class_name') or class_data.get('name', '')

                            # Check if data is already structured
                            if 'schedule_items' in class_data:
                                for item in class_data.get('schedule_items', []):
                                    schedule_items.append(ScheduleItem(
                                        day=item.get('day'),
                                        start=item.get('start'),
                                        end=item.get('end'),
                                        room=item.get('room')
                                    ))
                                lecturers = class_data.get('lecturer', [])
                            # Fallback to parsing raw strings
                            else:
                                schedule_text = class_data.get('schedule', '')
                                rooms_text = class_data.get('rooms', '')
                                schedule_lines = schedule_text.split('\n') if schedule_text else []
                                room_lines = rooms_text.split('\n') if rooms_text else []
                                
                                for i, schedule_line in enumerate(schedule_lines):
                                    if schedule_line.strip():
                                        match = re.match(r'(\w+),\s*([\d\.]+)-([\d\.]+)', schedule_line.strip())
                                        if match:
                                            day, start_time, end_time = match.groups()
                                            room = room_lines[i].strip() if i < len(room_lines) else ""
                                            schedule_items.append(ScheduleItem(
                                                day=day, start=start_time, end=end_time, room=room
                                            ))
                                
                                lecturers_text = class_data.get('lecturers', '')
                                if lecturers_text:
                                    lecturers = [lect.strip().lstrip('- ') for lect in lecturers_text.split('\n') if lect.strip()]

                            class_obj = Class(
                                name=class_name,
                                schedule_items=schedule_items,
                                lecturer=lecturers
                            )
                            classes.append(class_obj)
                        
                        course = Course(
                            course_code=course_data.get('course_code', ''),
                            curriculum=course_data.get('curriculum', ''),
                            name=course_data.get('name', ''),
                            description='',
                            prerequisite='',
                            credit=int(course_data.get('credit', 0)),
                            term=int(course_data.get('term', 0)),
                            classes=classes
                        )
                        converted_courses.append(course)
                        
                    except Exception as course_error:
                        yield format_sse({
                            "type": "warning", 
                            "message": f"Error converting course {course_data.get('name', 'Unknown')}: {str(course_error)}"
                        }, event='log')
                        continue
                
                period_instance.courses = converted_courses
                period_instance.last_update_at = datetime.datetime.now(datetime.timezone.utc)
                period_instance.save()
                
                yield format_sse({
                    "type": "success", 
                    "message": f"Successfully saved {len(converted_courses)} courses to database."
                }, event='log')
                
            except Exception as db_error:
                yield format_sse({
                    "type": "error", 
                    "message": f"Error saving to database: {str(db_error)}"
                }, event='log')

    return Response(stream_with_context(generate_logs_and_save(user, username, password)), content_type='text/event-stream')

@router_scraper.route('/scrape-siak-ng/status', methods=['GET'])
def scraper_status():
    """Simple status check for the scraper service."""
    return jsonify({
        "message": "SIAK NG scraper service is running",
        "version": "1.0"
    }), 200
