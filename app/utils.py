import os
import re
from flask import current_app as app

from app.jwt_utils import decode_token, encode_token

from models.major import Major
from models.period import Period
from models.user import User
from scraper.main import scrape_courses


def generate_token(user_id, major_id):
    token = encode_token({
        'user_id': str(user_id),
        'major_id': str(major_id),
    })
    return token


def extract_header_data(header):
    try:
        header_type, value = header['Authorization'].split()
        data = decode_token(value)
    except:
        return None

    return data

def get_user_id(request):
    data = extract_header_data(request.headers)
    if data is not None and 'user_id' in data:
        return data['user_id']
    return None

def process_sso_profile(sso_profile):
    period_name = app.config["ACTIVE_PERIOD"]
    user_npm = sso_profile["attributes"]["npm"]
    major_name = sso_profile["attributes"]["study_program"]
    major_kd_org = sso_profile["attributes"]["kd_org"]

    major = Major.objects(kd_org=major_kd_org).first()
    if major is None:
        major = Major(name=major_name, kd_org=major_kd_org)
        major.save()

    period_detail = Period.objects(
        major_id=major.id, name=period_name, is_detail=True).first()
    period_not_detail = Period.objects(
        major_id=major.id, name=period_name, is_detail=False).first()

    if period_detail is None:
        if period_not_detail is None:
            courses, is_detail = scrape_courses(major_kd_org, period_name)

            if not courses:
                result = {
                    "err": True,
                    "major_name": major_name
                }
                return result
        else:
            courses, is_detail = scrape_courses(
                major_kd_org, period_name, skip_not_detail=True)

        if courses:
            period = Period(
                major_id=major.id,
                name=period_name,
                courses=courses,
                is_detail=is_detail
            )
            period.save()

    user = User.objects(npm=user_npm).first()
    if user is None:
        user = User(
            name=sso_profile["attributes"]["ldap_cn"],
            username=sso_profile["username"],
            npm=user_npm,
            batch=f"20{user_npm[:2]}",
            major=major,
        )
        user.save()

    token = generate_token(user.id, user.major.id)
    result = {
        "user_id": str(user.id),
        "major_id": str(user.major.id),
        "token": token
    }

    return result


def get_app_config(varname):
    return app.config.get(varname)


def generate_admin_jwt():
    token = encode_token({
        'credentials': os.environ.get("ADMIN_CREDENTIAL_VERIFICATION")
    })
    return token


def normalize_str(s: str) -> str:
    if not s:
        return ""
    return re.sub(r'[^a-zA-Z0-9]', '', s.lower())


def __match_category(course, categories: list[str]) -> bool:
    if not categories:
        return True
    course_category = (course.category or '').strip().lower()
    return course_category in categories


def __match_exact_words(words: list[str], text: str) -> bool:
    return all(
        re.search(r'\b' + re.escape(w) + r'\b', text, re.IGNORECASE)
        for w in words
    )


def __match_exact_query(course, q_words: list[str]) -> bool:
    c_name = course.name or ''
    c_code = course.course_code or ''

    if __match_exact_words(q_words, f"{c_name} {c_code}"):
        return True

    return any(
        __match_exact_words(q_words, f"{c_name} {cls.name or ''}")
        for cls in course.classes
    )


def __match_fuzzy_query(course, q: str, q_words: list[str]) -> bool:
    c_name = course.name or ''
    c_code = course.course_code or ''
    q_norm = normalize_str(q)

    if q_norm and (q_norm in normalize_str(c_name) or q_norm in normalize_str(c_code)):
        return True
    if all(w in f"{c_name} {c_code}".lower() for w in q_words):
        return True

    for cls in course.classes:
        combined_raw = f"{c_name} {cls.name or ''}".lower()
        if q_norm and q_norm in normalize_str(combined_raw):
            return True
        if all(w in combined_raw for w in q_words):
            return True

    return False


def __match_course_query(course, course_queries: list[str], is_fuzzy: bool = False) -> bool:
    """
    Search courses
    - is_fuzzy=False: Harus exact courses (word boundary).
    - is_fuzzy=True: Bisa fuzzy search.
    """
    if not course_queries:
        return True

    for q in course_queries:
        q_words = [w.lower() for w in q.split() if w]
        if not q_words:
            continue

        matched = (
            __match_fuzzy_query(course, q, q_words)
            if is_fuzzy
            else __match_exact_query(course, q_words)
        )
        if matched:
            return True

    return False


def __match_sks(course, sks: int | None, sks_op: str) -> bool:
    if sks is None:
        return True

    c_credit = course.credit if course.credit is not None else 0
    if sks_op == 'eq':
        return c_credit == sks
    elif sks_op == 'lt':
        return c_credit < sks
    elif sks_op == 'gt':
        return c_credit > sks
    return True


def __is_day_valid(item, days: list[str]) -> bool:
    if not days:
        return True
    return (item.day or '').strip().lower() in days


def __is_time_valid(item, start_time: str | None, end_time: str | None) -> bool:
    item_start = item.start or ''
    item_end = item.end or ''
    if start_time and item_start < start_time:
        return False
    if end_time and item_end > end_time:
        return False
    return True


def __is_class_schedule_valid(
    cls,
    days: list[str],
    start_time: str | None,
    end_time: str | None,
    is_strict_time: bool = False,
    is_strict_days: bool = False,
) -> bool:
    items = cls.schedule_items
    if not items:
        return False

    def valid_day(item): return __is_day_valid(item, days)
    def valid_time(item): return __is_time_valid(item, start_time, end_time)

    # Semua sesi harus valid di hari & jam
    if is_strict_time and is_strict_days:
        return all(valid_day(item) and valid_time(item) for item in items)

    # Semua sesi valid di jam, minimal 1 sesi valid di hari
    if is_strict_time:
        return any(valid_day(item) for item in items) and all(valid_time(item) for item in items)

    # Semua sesi valid di hari, minimal 1 sesi valid di jam
    if is_strict_days:
        return all(valid_day(item) for item in items) and any(valid_time(item) for item in items)

    # Minimal 1 sesi valid di hari & jam sekaligus
    return any(valid_day(item) and valid_time(item) for item in items)


def __filter_classes_by_schedule(
    classes,
    days: list[str],
    start_time: str | None,
    end_time: str | None,
    is_strict_time: bool = False,
    is_strict_days: bool = False,
) -> list:
    has_time_filter = bool(days or start_time or end_time)
    if not has_time_filter:
        return [cls.serialize() for cls in classes]

    return [
        cls.serialize()
        for cls in classes
        if __is_class_schedule_valid(
            cls, days, start_time, end_time, is_strict_time, is_strict_days
        )
    ]


def filter_courses_data(courses, args):
    """
    Filtering berdasarkan query parameters:
    - categories: Kategori kelas (Kelas Internal, Kelas External, Kelas Bersama), bisa multiple
    - courses: Nama atau Kode Mata Kuliah, bisa multiple
    - fuzzy: Jika true, pencarian nama mata kuliah bisa fuzzy search
    - days: Hari kuliah (Senin, Selasa, dll.), bisa multiple
    - strict_days: Jika true, semua sesi kelas HARUS berada di hari yang diminta
    - start_time & end_time: Rentang jam (format HH:MM atau HH.MM)
    - strict_time: Jika true, semua sesi kelas HARUS berada di dalam rentang jam kuliah
    - sks: Jumlah SKS (integer)
    - sks_op: Operator SKS ('eq', 'lt', 'gt')
    """
    category_param = args.get('categories')
    categories = [c.strip().lower() for c in category_param.split(',')] if category_param else []

    course_param = args.get('courses')
    course_queries = [c.strip() for c in course_param.split(',')] if course_param else []
    
    is_fuzzy = str(args.get('fuzzy', 'false')).lower() in ['true', '1', 'yes']

    day_param = args.get('days')
    days = [d.strip().lower() for d in day_param.split(',')] if day_param else []
    
    is_strict_days = str(args.get('strict_days', 'false')).lower() in ['true', '1', 'yes']

    start_time = args.get('start_time')
    end_time = args.get('end_time')

    is_strict_time = str(args.get('strict_time', 'false')).lower() in ['true', '1', 'yes']

    sks = args.get('sks', type=int)
    sks_op = args.get('sks_op', 'eq').lower()

    filtered_courses = []

    for course in courses:
        if not __match_category(course, categories):
            continue

        if not __match_course_query(course, course_queries, is_fuzzy):
            continue

        if not __match_sks(course, sks, sks_op):
            continue

        valid_classes = __filter_classes_by_schedule(
            course.classes, days, start_time, end_time, is_strict_time, is_strict_days
        )

        has_time_filter = bool(days or start_time or end_time)
        if has_time_filter and not valid_classes:
            continue

        serialized_course = course.serialize()
        serialized_course['classes'] = valid_classes
        filtered_courses.append(serialized_course)

    return filtered_courses