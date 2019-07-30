import os
import time
from flask import (
    Blueprint,
    current_app as app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for
)
from werkzeug.utils import secure_filename

from models.major import Major
from models.period import Period
from uploader.decorators import require_jwt_cookie
from uploader.utils import (
    check_uploader,
    generate_token,
    get_sso_logout_url
)
from scraper.main import get_period_and_kd_org, create_courses
from sso.utils import authenticate, get_cas_client


router_uploader = Blueprint(
    'router_uploader', __name__, template_folder="templates")


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {".html"}
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

        npm = sso_profile["attributes"]["npm"]
        if (sso_profile is not None) and check_uploader(npm):
            token = generate_token(sso_profile)
            r = make_response(redirect(url_for("router_uploader.upload")))
            r.set_cookie("__token", token)
            return r

    flash("Apa yang kamu lakukan di sini?")
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
            flash("File error.")
            return redirect(request.url)

        file_ = request.files["file"]

        if file_.filename == "":
            flash("File kosong.")
            return redirect(request.url)

        if file_ and allowed_file(file_.filename):

            if not os.path.isdir(app.config["UPLOAD_FOLDER"]):
                os.mkdir(app.config["UPLOAD_FOLDER"])

            html = file_.read()
            period, kd_org = get_period_and_kd_org(html)
            role = check_uploader(profile["npm"])

            if (period == app.config["ACTIVE_PERIOD"]) and (kd_org == profile["kd_org"] or role == "admin"):
                courses = create_courses(html, is_detail=True)
                if not courses:
                    flash("Error, hubungi admin. Sertakan file ini.")
                    return redirect(request.url)

                major = Major.objects(kd_org=kd_org).first()
                if major is None:
                    flash("Login susun jadwal beneran dulu ya.")
                    return redirect(request.url)

                instance = Period.objects(
                    major_id=major.id,
                    name=period,
                    is_detail=True
                ).first()

                if instance:
                    instance.courses = courses
                else:
                    instance = Period(
                        major_id=major.id,
                        name=period,
                        courses=courses,
                        is_detail=True
                    )
                instance.save()

                timestamp = int(time.time())
                filename = f"{kd_org}_{timestamp}_{secure_filename(file_.filename)}"
                file_.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

            else:
                flash("Periode salah atau jurusan tidak sesuai.")
                return redirect(request.url)

            flash("Berhasil..!!")
            return redirect(request.url)

        flash("Gagal. File salah atau hubungi admin.")
        return redirect(request.url)

    return render_template("upload.html", profile=profile)
