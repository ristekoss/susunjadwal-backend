import mongoengine as mongo
from datetime import datetime
from .user import User

class Review(mongo.Document):
    user = mongo.ReferenceField("User", required=True)
    rating = mongo.IntField(min_value=1, max_value=5, required=True)
    comment = mongo.StringField(max_length=1000)
    created_at = mongo.DateTimeField(default=datetime.utcnow)
    reviewed = mongo.BooleanField(default=False)
    

    def serialize(self):
        return {
            "user_id": str(self.user.id),
            "user_name": str(self.user.name),
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat(),
            "reviewed": self.reviewed
        }