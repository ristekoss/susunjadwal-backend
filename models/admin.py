import mongoengine as mongo
from werkzeug.security import check_password_hash


class Admin(mongo.Document):
    username = mongo.StringField(max_length=256, required=True)
    password = mongo.StringField(max_length=256, required=True)

    def check_password(self, password):
        return check_password_hash(self.password, password)