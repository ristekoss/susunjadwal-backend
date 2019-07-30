import os
from flask import (
    Blueprint,
    current_app as app,
    make_response,
    redirect,
    render_template,
    request,
    url_for
)
from werkzeug.utils import secure_filename

from uploader.utils import (
    generate_token,
    get_sso_logout_url,
    require_jwt_cookie
)
from sso.utils import authenticate, get_cas_client


router_uploader = Blueprint(
    'router_uploader', __name__, template_folder="templates")


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {".pdf"}
    _, ext = os.path.splitext(filename)
    return ext in ALLOWED_EXTENSIONS


@router_uploader.route("/__uploader/login")
def login():
    return render_template("login.html")


@router_uploader.route("/__uploader/auth")
def auth():
    ticket = request.args.get("ticket")
    service_url = url_for("router_uploader.auth", _external=True)

    if (ticket is not None):
        client = get_cas_client(service_url)
        sso_profile = authenticate(ticket, client)

        if sso_profile is not None:
            token = generate_token(sso_profile)
            r = make_response(redirect(url_for("router_uploader.upload")))
            r.set_cookie("__token", token)
            return r

    return redirect(url_for("router_uploader.login"))


@router_uploader.route("/__uploader/logout")
def logout():
    logout_url = get_sso_logout_url()
    r = make_response(redirect(logout_url))
    r.set_cookie("__token", "")
    return r


@router_uploader.route("/__uploader/upload", methods=['GET', 'POST'])
@require_jwt_cookie
def upload(profile):
    if request.method == "POST":
        if "file" not in request.files:
            return redirect(request.url)

        file_ = request.files["file"]

        # if user does not select file, browser also
        # submit an empty part without filename
        if file_.filename == "":
            return redirect(request.url)

        if file_ and allowed_file(file_.filename):
            if not os.path.isdir(app.config["UPLOAD_FOLDER"]):
                os.mkdir(app.config["UPLOAD_FOLDER"])

            filename = secure_filename(file_.filename)

            # TO-DO process file_
            file_.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            return render_template("upload.html", info="Berhasil..!!")

        return render_template("upload.html", info="Gagal. Cek format file atau hubungi admin.")

    return render_template("upload.html")
