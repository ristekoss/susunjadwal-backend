import html
from flask import (
    Blueprint,
    jsonify,
    request
)

from app.decorators import require_jwt_token, require_same_user_id
from app.jwt_utils import decode_token
from app.services.scrapper.schedule_scrapper import ScheduleScrapperServices
from models.period import Period
from models.user import User
from models.major import Major
from models.user_schedule import UserSchedule
from app.utils import get_user_id, get_app_config

router_main = Blueprint('router_sunjad', __name__)

"""
Provides course list by major kd_org.
The kd_org list is provided in sso/additional_info.json
"""
@router_main.route('/majors/<major_kd_org>/courses_by_kd', methods=['GET'])
@require_jwt_token
def get_courses_by_kd(major_kd_org):
    active_period = get_app_config("ACTIVE_PERIOD")
    major = Major.objects(
        kd_org=major_kd_org
    ).first()
    if major is None: # there is still no user from desired major that already use update matkul
        return ({}, 200)
    period = Period.objects(
        major_id=major.id,
        name=active_period,
        is_detail=True
    ).first()
    if period is None: # alternatives, check from different scraping method, currently not used
        period = Period.objects(
            major_id=major.id,
            name=active_period,
            is_detail=False
        ).first()
    if period is None: # if still not exist, user from the desired major must scrape the course first
        return ({}, 200)

    return (jsonify(period.serialize()), 200)


@router_main.route('/majors/<major_id>/courses', methods=['GET'])
@require_jwt_token
def get_courses(major_id):
    active_period = get_app_config("ACTIVE_PERIOD")
    period = Period.objects(
        major_id=major_id,
        name=active_period,
        is_detail=True
    ).first()
    if period is None:
        period = Period.objects(
            major_id=major_id,
            name=active_period,
            is_detail=False
        ).first()
    return (jsonify(period.serialize()), 200)

"""
Provides all course list available in database.
"""
@router_main.route('/periods', methods=['GET'])
def get_list_period():
    period = Period.objects().all()
    data = []
    for p in period:
        data.append(p.serialize())
    return(jsonify(period.serialize()), 200)

@router_main.route('/users/<user_id>/user_schedule', methods=['POST'])
@require_jwt_token
@require_same_user_id
def save_user_schedule(user_id):
    data = request.json
    active_period = get_app_config("ACTIVE_PERIOD")
    user_schedule = UserSchedule(user_id=user_id, period=active_period)
    for item in data['schedule_items']:
        user_schedule.add_schedule_item(**item)
    user_schedule.save()

    return (jsonify({
        'id': str(user_schedule.id),
    }), 201)


@router_main.route('/user_schedules/<user_schedule_id>', methods=['GET'])
def get_user_schedule_detail(user_schedule_id):
    user_schedule = UserSchedule.objects(id=user_schedule_id).first()
    request_user_id = get_user_id(request)
    return (jsonify({
        'user_schedule': {
            **user_schedule.serialize(),
            "has_edit_access": str(user_schedule.user_id.id) == request_user_id
        }
    }), 200)


@router_main.route('/users/<user_id>/user_schedules')
@require_jwt_token
@require_same_user_id
def get_user_schedule_list(user_id):
    schedules = UserSchedule.objects(user_id=user_id, deleted=False).all()
    data = []
    for schedule in schedules:
        data.append(schedule.serialize())
    return (jsonify({
        'user_schedules': data
    }), 200)


@router_main.route('/users/<user_id>/user_schedules/<user_schedule_id>', methods=['DELETE'])
@require_jwt_token
@require_same_user_id
def delete_user_schedule(user_id, user_schedule_id):
    user_schedule = UserSchedule.objects(user_id=user_id, id=user_schedule_id).first()
    if user_schedule is None:
        return jsonify({'message': 'Schedule not found.'}), 404
    user_schedule.deleted = True
    user_schedule.save()
    return (jsonify(), 204)


@router_main.route('/users/<user_id>/user_schedules/<user_schedule_id>/change_name', methods=['POST'])
@require_jwt_token
@require_same_user_id
def rename_user_schedule(user_id, user_schedule_id):
    data = request.json
    user_schedule = UserSchedule.objects(user_id=user_id, id=user_schedule_id).first()
    if user_schedule is None:
        return jsonify({'message': 'Schedule not found.'}), 404
    user_schedule.name = html.escape(data["name"])
    user_schedule.save()
    return (jsonify({
        'user_schedule': user_schedule.serialize()
    }), 200)


@router_main.route('/users/<user_id>/user_schedules/<user_schedule_id>', methods=['PUT'])
@require_jwt_token
@require_same_user_id
def edit_user_schedule(user_id, user_schedule_id):
    active_period = get_app_config("ACTIVE_PERIOD")
    user_schedule = UserSchedule.objects(id=user_schedule_id).first()
    # If the schedule doesn't exist or the user is mismatched,
    # create a new one with the same items.
    if user_schedule is None:
        user_schedule = UserSchedule(user_id=user_id, period=active_period)
    elif str(user_schedule.user_id.id) != user_id:
        name = f'{user_schedule.name} (copied)'
        user_schedule = UserSchedule(user_id=user_id, name=name, period=active_period)
    data = request.json
    user_schedule.clear_schedule_item()
    for editedScheduleItem in data['schedule_items']:
        user_schedule.add_schedule_item(**editedScheduleItem)
    user_schedule.save()

    return (jsonify({
        'user_schedule': user_schedule.serialize()
    }), 200)

@router_main.route('/scrape-schedule', methods=['POST'])
@require_jwt_token
def scrap_all_schedule():
    header_data = request.headers
    user_data = decode_token(header_data["Authorization"].split()[1])
    user: User = User.objects(id=user_data['user_id']).first()
    data = request.json
    username = data['username']
    password = data['password']
    response, status_code = ScheduleScrapperServices.scrape_course_page(
        user=user,
        username=username,
        password=password
    )
    return jsonify(response), status_code

@router_main.route('/courses', methods=['GET'])
def get_all_courses():
    active_period = get_app_config("ACTIVE_PERIOD")
    periods = Period.objects.all()
    all_courses = []
    for period in periods:
        for course in period.courses:
            all_courses.append(course.serialize_ulas_kelas())
    return (jsonify({
        'courses': all_courses
    }), 200)