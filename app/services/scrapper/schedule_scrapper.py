import datetime
import json
import requests
import ssl
from threading import Thread
from typing import Tuple

from app.utils import get_app_config
from app.message_queue import request_mq_channel_from_pool, create_new_mq_channel
from models.major import Major
from models.period import Period
from models.user import User
from scraper.main import scrape_courses_with_credentials, AUTH_URL, generate_desc_prerequisite

class TLSAdapter(requests.adapters.HTTPAdapter):

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = ctx
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

class ScheduleScrapperServices:
    @classmethod
    def create_schedule_scrapper_consumer_thread(cls, app, faculty_name, routing_key):

        exchange_name = app.config.get("UPDATE_COURSE_LIST_EXCHANGE_NAME")
        active_period = app.config.get("ACTIVE_PERIOD")
        channel = create_new_mq_channel(app)
        queue_name = faculty_name.lower()
        channel.queue_declare(queue_name, durable=True)
        channel.queue_bind(
            exchange=exchange_name, queue=queue_name, routing_key=routing_key
        )

        def callback(ch, method, properties, body):
            data = json.loads(body)
            now = datetime.datetime.utcnow()
            username = data['username']
            password = data['password']
            major_id = data['major_id']
            period = Period.objects(major_id=major_id, name=active_period, is_detail=True).first()
            if period is None:
                period = Period(
                    major_id=major_id,
                    is_detail=True,
                    name=active_period,
                )
            if period.last_update_at:
                time_difference = now - period.last_update_at
                if time_difference.seconds < 300:
                    return
            courses = scrape_courses_with_credentials(active_period, username, password)
            period.courses = courses
            period.last_update_at = now
            period.save()
            app.logger.info(f"Done scrapping kd_org: {method.routing_key}; period: {active_period}; at: {now} UTC")
            # Generate description and prerequisite data for all courses
            generate_desc_prerequisite(period, username, password)

        channel.basic_consume(
            queue=queue_name, on_message_callback=callback, auto_ack=True
        )
        return Thread(target=channel.start_consuming, daemon=True)

    @classmethod
    def init_service(cls, app):
        exchange_name = app.config.get("UPDATE_COURSE_LIST_EXCHANGE_NAME")
        with request_mq_channel_from_pool() as channel:
            channel.exchange_declare(exchange=exchange_name, exchange_type='topic')

        list_faculty = app.config.get("FACULTY_EXCHANGE_ROUTE")
        for k, v in list_faculty.items():
            thread = cls.create_schedule_scrapper_consumer_thread(
                app=app,
                faculty_name=k,
                routing_key=v
            )
            thread.start()

    @classmethod
    def scrape_course_page(cls, user: User, username: str, password: str) -> Tuple[dict, int]:
        now = datetime.datetime.utcnow()
        req = requests.Session()
        # req.verify = False
        # req.trust_env = False
        # req.mount('https://', TLSAdapter())
        r = req.post(
            AUTH_URL, 
            data={'u': username, 'p': password},
            # headers={'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36 Edg/103.0.1264.49"},
            verify=False
        )
        if "Login Failed" in r.text:
            return {
                       'success': False,
                       'message': "Login gagal"
                   }, 400
        if user.last_update_course_request_at:
            time_difference = now - user.last_update_course_request_at
            if time_difference.seconds < 300:
                return {
                           'success': False,
                           'message': "Anda sudah melakukan permintaan sebelumnya, harap tunggu 5 menit"
                       }, 400
        exchange_name = get_app_config("UPDATE_COURSE_LIST_EXCHANGE_NAME")
        major: Major = user.major
        kd_org = major.kd_org
        message = {
            'major_id': str(major.id),
            'username': username,
            'password': password,
        }
        with request_mq_channel_from_pool() as channel:
            message = json.dumps(message)
            channel.basic_publish(exchange=exchange_name, routing_key=kd_org, body=message)
        user.last_update_course_request_at = now
        user.save()
        return {
                   'success': True
               }, 200
