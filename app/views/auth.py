import pydantic
from flask import (
    Blueprint,
    jsonify,
    request
)

from app.exceptions.auth import UserNotFound, KdOrgNotFound
from app.services.auth.auth import AuthServices, AuthCompletionData
from app.utils import process_sso_profile, get_app_config
from sso.utils import (
    authenticate,
    get_cas_client,
)

router_auth = Blueprint('router_auth', __name__)


@router_auth.route("/auth/", methods=['POST'])
def auth():
    data = request.json
    ticket = data.get("ticket")
    service_url = data.get("service_url")
    if (ticket is not None) and (service_url is not None):
        client = get_cas_client(service_url)
        sso_profile = authenticate(ticket, client)
        if sso_profile is not None:
            user_data = process_sso_profile(sso_profile)
            return (jsonify(user_data), 200)

    return (jsonify(), 400)

@router_auth.route("/auth/v2/", methods=['POST'])
def auth_v2():
    data = request.json
    ticket = data.get("ticket")
    service_url = data.get("service_url")
    if (ticket is not None) and (service_url is not None):
        client = get_cas_client(service_url)
        sso_profile = authenticate(ticket, client)
        if sso_profile is not None:
            user_data,status_code = AuthServices.process_sso_auth(sso_profile)
            return jsonify(user_data),status_code

    return jsonify(), 400

@router_auth.route("/auth/completion/", methods=['POST'])
def auth_completion():
    data = AuthCompletionData(**request.json)
    try:
        response = AuthServices.process_auth_completion(data)
        return jsonify(response),200
    except (UserNotFound, KdOrgNotFound) as e1:
        return jsonify({
            'message':str(e1)
        }), 400
    except pydantic.error_wrappers.ValidationError as e2:
        return jsonify(e2.errors()), 400


@router_auth.route("/faculties", methods=["GET"])
def list_faculties():
    kd_org_data: dict = get_app_config("FACULTY_KD_ORG")
    return jsonify(list(kd_org_data.keys())), 200

@router_auth.route("/faculty/<faculty_idx>/majors", methods=["GET"])
def list_majors(faculty_idx):
    converted_faculty_idx = int(faculty_idx)
    try:
        faculty_majors: dict = list(get_app_config("FACULTY_KD_ORG").items())[converted_faculty_idx][1]
        return jsonify(faculty_majors), 200
    except IndexError:
        return jsonify(), 400