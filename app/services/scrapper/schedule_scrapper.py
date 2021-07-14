import datetime
from typing import Tuple
from flask import current_app as app

from models.major import Major
from models.period import Period
from models.user import User
from scraper.main import scrape_courses_with_credentials


class ScheduleScrapperServices:
    @classmethod
    def scrape_course_page(cls, user: User, username: str, password: str) -> Tuple[dict, int]:
        active_period = app.config.get("ACTIVE_PERIOD")
        major: Major = user.major
        courses = scrape_courses_with_credentials(active_period, username, password)
        period = Period.objects(major_id=major.id, name=active_period, is_detail=True).first()
        if period is None:
            period = Period(
                major_id=major.id,
                is_detail=True,
                name=active_period,
            )
        period.courses = courses
        period.last_update_at = datetime.datetime.now()
        period.save()

        return {
            'success': True
        }, 200



