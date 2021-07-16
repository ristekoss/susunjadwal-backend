from widgets.flask_pika_mod import Pika as FPika
import pika

fpika = FPika()


def init_pika(app):
    fpika.init_app(app)


def create_new_mq_channel(app):
    connection_parameters = app.config.get("FLASK_PIKA_PARAMS")
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            **connection_parameters
        ))
    channel = connection.channel()
    return channel


def request_mq_channel_from_pool():
    return fpika.channel()
