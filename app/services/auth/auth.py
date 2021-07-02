import uuid

from app import app
from app.utils import generate_token
from models.major import Major
from models.user import User


class AuthServices:
    @classmethod
    def process_sso_auth(cls, sso_profile) -> dict:
        user_name = sso_profile["username"]
        user = User.objects(username=user_name).first()
        if user is None:
            full_name = sso_profile['attributes']['ldap_cn']
            user = User(
                name=full_name,
                username=user_name
            )
            try:
                user_npm = sso_profile["attributes"]["npm"]
                major_name = sso_profile["attributes"]["study_program"]
                major_kd_org = sso_profile["attributes"]["kd_org"]
            except KeyError:
                completion_id = uuid.uuid4()
                user.completion_id = completion_id
                user.save()
                return {
                    'user_name':user_name,
                    'full_name':full_name,
                    'completion_id':str(completion_id)
                }
            user.npm = user_npm
            user.batch = f"20{user_npm[:2]}"
            major = Major.objects(kd_org=major_kd_org).first()
            if major is None:
                major = Major(name=major_name, kd_org=major_kd_org)
                major.save()

            user.major = major
            user.save()

        if user.completion_id is not None:
            return {
                'user_name': user.username,
                'full_name': user.name,
                'completion_id':str(user.completion_id)
            }

        token = generate_token(user.id, user.major.id)
        result = {
            "user_id": str(user.id),
            "major_id": str(user.major.id),
            "token": token
        }
        return result

