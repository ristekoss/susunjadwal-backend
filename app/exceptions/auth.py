class UserNotFound(BaseException):
    def __init__(self):
        super().__init__("user not found")


class KdOrgNotFound(BaseException):
    def __init__(self):
        super().__init__("kd org not found")