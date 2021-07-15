import uuid
from typing import Tuple

from app.exceptions.auth import UserNotFound, KdOrgNotFound
from app.utils import generate_token, get_app_config
from models.major import Major
from models.period import Period
from models.user import User
from pydantic import BaseModel, validator, constr


class AuthCompletionData(BaseModel):
    completion_id: uuid.UUID
    npm: constr(max_length=10,min_length=10)
    kd_org: str

    @validator("npm")
    def npm_must_be_numeric_only_and_minimum_10(cls, v: str):
        if not v.isnumeric():
            raise ValueError("npm must be numeric")
        return v


class AuthServices:
    @classmethod
    def process_sso_auth(cls, sso_profile) -> Tuple[dict, int]:
        user_name = sso_profile["username"]
        period_name = get_app_config("ACTIVE_PERIOD")
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
                }, 201
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
            }, 201

        major = user.major

        period = Period.objects(
            major_id=major.id,
            name=period_name,
            is_detail=True
        ).first()

        token = generate_token(user.id, user.major.id)

        result = {
            "user_id": str(user.id),
            "major_id": str(user.major.id),
            "token": token
        }

        if period is None:
            result = {
                **result,
                "err": True,
                "major_name": major.name
            }
        return result, 200

    @classmethod
    def process_auth_completion(cls,data: AuthCompletionData) -> dict:
        user = User.objects(completion_id=data.completion_id).first()
        period_name = get_app_config("ACTIVE_PERIOD")
        if user is None:
            raise UserNotFound()
        base_kd_org_data = get_app_config("BASE_KD_ORG")
        try:
            kd_org_data = base_kd_org_data[data.kd_org]
        except KeyError:
            raise KdOrgNotFound()

        major = Major.objects(kd_org=data.kd_org).first()
        if major is None:
            major = Major(name=kd_org_data["study_program"], kd_org=data.kd_org)
            major.save()

        user.npm = data.npm
        user.major = major
        user.completion_id = None
        user.batch = f"20{data.npm[:2]}"
        user.save()

        period = Period.objects(
            major_id=major.id,
            name=period_name,
            is_detail=True
        ).first()

        token = generate_token(user.id, user.major.id)
        result = {
            "user_id": str(user.id),
            "major_id": str(major.id),
            "token": token
        }
        if period is None:
            result = {
                **result,
                "err": True,
                "major_name": major.name
            }
        return result







