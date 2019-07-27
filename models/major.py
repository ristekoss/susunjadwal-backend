import mongoengine as mongo


class Major(mongo.Document):
    name = mongo.StringField(max_length=256)
    kd_org = mongo.StringField(max_length=16)  # some code for study program
