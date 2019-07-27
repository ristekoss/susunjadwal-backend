from flask import (
    Blueprint,
    current_app as app,
    jsonify,
    request
)

from app.decorators import require_same_user_id
from app.jwt_utils import require_jwt_token
from models.period import Period
from models.user_schedule import UserSchedule


router_main = Blueprint('router_sunjad', __name__)


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


@router_main.route('/users/<user_id>/user_schedule', methods=['POST'])
@require_jwt_token
@require_same_user_id
def save_user_schedule(user_id):
    data = request.json
    user_schedule = UserSchedule(user_id=user_id)
    for item in data['schedule_items']:
        user_schedule.add_schedule_item(**item)
    user_schedule.save()

    return (jsonify({
        'id': str(user_schedule.id),
    }), 201)


@router_main.route('/user_schedules/<user_schedule_id>')
def get_user_schedule_detail(user_schedule_id):
    user_schedule = UserSchedule.objects(id=user_schedule_id).first()
    return (jsonify({
        'user_schedule': user_schedule.serialize()
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
    user_schedule = UserSchedule.objects(id=user_schedule_id).first()
    user_schedule.deleted = True
    user_schedule.save()
    return (jsonify(), 204)


@router_main.route('/users/<user_id>/user_schedules/<user_schedule_id>/change_name', methods=['POST'])
@require_jwt_token
@require_same_user_id
def rename_user_schedule(user_id, user_schedule_id):
    data = request.json
    user_schedule = UserSchedule.objects(id=user_schedule_id).first()
    user_schedule.name = data["name"]
    user_schedule.save()
    return (jsonify({
        'user_schedule': user_schedule.serialize()
    }), 200)


def get_app_config(varname):
    return app.config.get(varname)
