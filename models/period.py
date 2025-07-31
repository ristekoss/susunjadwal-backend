import mongoengine as mongo


class ScheduleItem(mongo.EmbeddedDocument):
    day = mongo.StringField(max_length=16)
    start = mongo.StringField(max_length=16)
    end = mongo.StringField(max_length=16)
    room = mongo.StringField(max_length=64)

    def serialize(self):
        return {
            "day": self.day,
            "start": self.start,
            "end": self.end,
            "room": self.room
        }


class Class(mongo.EmbeddedDocument):
    name = mongo.StringField(max_length=128)
    schedule_items = mongo.ListField(mongo.EmbeddedDocumentField(ScheduleItem))
    lecturer = mongo.ListField(mongo.StringField(max_length=128))

    def __get_schedule_items(self):
        data = []
        for item in self.schedule_items:
            data.append(item.serialize())
        return data

    def serialize(self):
        return {
            "name": self.name,
            "lecturer": self.lecturer,
            "schedule_items": self.__get_schedule_items()
        }


class Course(mongo.EmbeddedDocument):
    course_code = mongo.StringField(max_length=16)
    curriculum = mongo.StringField(max_length=32)
    name = mongo.StringField(max_length=128)
    description = mongo.StringField(max_length=2048)
    prerequisite = mongo.StringField(max_length=256)
    credit = mongo.IntField()
    term = mongo.IntField()
    classes = mongo.ListField(mongo.EmbeddedDocumentField(Class))

    def __get_classes(self):
        data = []
        for class_ in self.classes:
            data.append(class_.serialize())
        return data

    def serialize(self):
        return {
            "name": self.name,
            "credit": self.credit,
            "term": self.term,
            "classes": self.__get_classes()
        }
    
    def serialize_ulas_kelas(self):
        return {
            "name": self.name,
            "credit": self.credit,
            "code": self.course_code,
            "curriculum": self.curriculum,
            "description": self.description,
            "prerequisite": self.prerequisite,
            "term": self.term
        }

class Period(mongo.Document):
    major_id = mongo.ReferenceField("Major")
    name = mongo.StringField(max_length=16)
    is_detail = mongo.BooleanField(default=False)
    courses = mongo.ListField(mongo.EmbeddedDocumentField(Course))
    last_update_at = mongo.DateTimeField(default=None)

    def __get_courses(self):
        data = []
        for course in self.courses:
            data.append(course.serialize())

        return data

    def serialize(self):
        return {
            "last_update_at": self.last_update_at.isoformat() + "Z" if self.last_update_at else None,
            "name": self.name,
            "is_detail": self.is_detail,
            "courses": self.__get_courses(),
        }
