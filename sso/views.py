from flask import (
    Blueprint,
    current_app as app,
    jsonify,
    render_template,
    request
)

from sso.utils import (
    authenticate,
    get_cas_client,
    process_sso_profile
)

router_sso = Blueprint('router_sso', __name__, template_folder="templates")


@router_sso.route("/auth/", methods=['POST'])
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
