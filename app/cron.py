from flask import (
    Blueprint,
    current_app as app
)

from models.major import Major
from models.period import Period
from scraper.main import scrape_courses

cron = Blueprint("cron", __name__)


@cron.cli.command("update_courses")
def update_courses():
    period_name = app.config["ACTIVE_PERIOD"]
    majors = Major.objects.all()
    for major in majors:
        major_kd_org = major.kd_org
        period_detail = Period.objects(
            major_id=major.id, name=period_name, is_detail=True).first()

        if period_detail is None:
            period_not_detail = Period.objects(
                major_id=major.id, name=period_name, is_detail=False).first()

            if period_not_detail is None:
                return

            courses, is_detail = scrape_courses(major_kd_org, period_name)
            if courses:
                if is_detail:
                    period = Period(
                        major_id=major.id,
                        name=period_name,
                        courses=courses,
                        is_detail=True
                    )
                    period.save()
                else:
                    period_not_detail.courses = courses
                    period_not_detail.save()
            return

        courses, is_detail = scrape_courses(
            major_kd_org, period_name, skip_not_detail=True)

        if courses:
            period_detail.courses = courses
            period_detail.save()
