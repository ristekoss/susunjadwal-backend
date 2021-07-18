import mongoengine as mongo


class User(mongo.Document):
    name = mongo.StringField(max_length=255)
    username = mongo.StringField(max_length=64)
    npm = mongo.StringField(max_length=20)
    batch = mongo.StringField(max_length=5)
    major = mongo.ReferenceField("Major")
    update_schedule_at = mongo.DateTimeField(default=None)
    completion_id = mongo.UUIDField(default=None)
    last_update_course_request_at = mongo.DateTimeField(default=None)


