import re
import requests
from bs4 import BeautifulSoup
import json
from scraper.playwright_renderer import render_with_playwright

BASE_URL = "https://slcm.ui.ac.id"
SCHEDULE_PAGE_URL = f"{BASE_URL}/akademik/schedule/class"
SCHEDULE_WHOLE_PAGE_URL = f"{BASE_URL}/akademik/schedule/class/whole"
API_CLASS_TABLE = f"{BASE_URL}/akademik/api/v1/class/table"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def _normalize_class_list(value):
    if isinstance(value, str):
        return value.split()
    return value or []

def _page_has_schedule(html_content):
    return "group-header-row" in html_content or "class-row" in html_content or "<tbody" in html_content

def login_slcm(session, username, password, whole=False, year=None, term=None):
    """Authenticate to SLCM and fetch course schedule data.

    Strategy (tried in order):
      1. Playwright browser automation (handles Keycloak OIDC SSO)
      2. Direct HTTP: fetch schedule page (may be server-rendered for some users)

    Args:
        whole: if True, fetch from the /whole page (all faculties).
               Default False (user's own faculty only).
        year: academic year (e.g. "2026"). If None, determined from page/env.
        term: term number (e.g. "1"). If None, determined from page/env.

    Returns JSON string from the API response (all class categories:
    internal, group, external), or HTML string fallback.
    """
    target_url = SCHEDULE_WHOLE_PAGE_URL if whole else SCHEDULE_PAGE_URL
    playwright_result = render_with_playwright(target_url, username, password, year=year, term=term)
    if playwright_result is not None:
        return playwright_result

    response = session.get(SCHEDULE_PAGE_URL, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=30)
    response.raise_for_status()
    html = response.text

    if _page_has_schedule(html):
        return html

    raise ValueError(
        "Unable to authenticate to SLCM or fetch schedule. "
        "Playwright (Chromium) is required. "
        "Install it via: pip install playwright && python -m playwright install chromium"
    )

def extract_period_name(html_or_json):
    try:
        data = json.loads(html_or_json)
        if isinstance(data, dict):
            meta = data.get("meta", data)
            period = meta.get("period") or meta.get("periodName") or meta.get("name", "")
            if period:
                return str(period)
            for key in ("period", "semester", "academicYear", "year"):
                val = data.get(key)
                if val:
                    return str(val)
        return None
    except (json.JSONDecodeError, ValueError, AttributeError):
        pass

    soup = BeautifulSoup(html_or_json, "html.parser")
    selection = soup.find("div", class_="v-select__selection")
    if selection and selection.text.strip():
        return selection.text.strip()
    option = soup.find("option", selected=True)
    if option and option.text.strip():
        return option.text.strip()
    return None

def extract_period_value(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    option = soup.find("option", selected=True)
    if option and option.get("value"):
        return option["value"]
    return None

def _parse_v1_api_response(data):
    """Parse the /akademik/api/v1/class/table JSON response.

    The API returns a flat list of class sections:
    {
      "data": [
        {
          "classcode": 810203,
          "classname": "MD1",
          "classlang": "Indonesia",
          "coursecode": "CSGE601010",
          "currcode": "06.00.12.01-2024",
          "orgcode": "06.00.12.01",
          "coursename": "Matematika Diskret 1",
          "forterm": 1,
          "sks": 3,
          "dates_rooms": ["Senin, 10.00-11.40 (A5.03 (Ged Baru))", ...],
          "lecturers": ["Rahmad Mahendra, S.Kom., ...", ...],
          ...
        },
        ...
      ],
      "message": "Table Class is successfuly!"
    }
    """
    if isinstance(data, dict):
        items = data.get("data") or data.get("courses") or data.get("results") or data.get("list") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []

    if not isinstance(items, list):
        items = []
        return []

    courses_map = {}

    for item in items:
        if not isinstance(item, dict):
            continue

        course_code = (
            item.get("coursecode") or
            item.get("courseCode") or
            item.get("code") or
            item.get("course_code") or
            item.get("kodeMk") or
            item.get("kode_mk", "")
        )
        if not course_code:
            continue

        course_name = (
            item.get("coursename") or
            item.get("courseName") or
            item.get("name") or
            item.get("course_name") or
            item.get("namaMk") or
            item.get("nama_mk", "")
        )
        credit = (
            item.get("sks") or
            item.get("credit") or
            item.get("creditValue") or
            item.get("kredit") or
            0
        )
        curriculum = (
            item.get("currcode") or
            item.get("curriculum") or
            item.get("kurikulum", "")
        )
        term = (
            item.get("forterm") or
            item.get("term") or
            item.get("semester") or
            0
        )
        category = (
            item.get("category") or
            item.get("kategori") or
            ""
        )

        course_key = (course_code, category)
        if course_key not in courses_map:
            courses_map[course_key] = {
                "course_code": course_code,
                "curriculum": curriculum,
                "name": course_name,
                "category": category,
                "credit": int(credit) if isinstance(credit, (int, float)) else 0,
                "term": int(term) if isinstance(term, (int, float)) else 0,
                "classes": [],
            }

        class_name = (
            item.get("classname") or
            item.get("className") or
            item.get("class") or
            item.get("nama") or
            item.get("kelas", "")
        )
        lecturers_raw = (
            item.get("lecturers") or
            item.get("lecturer") or
            item.get("dosen") or
            item.get("instructor") or
            []
        )
        if isinstance(lecturers_raw, str):
            lecturers_raw = [l.strip() for l in lecturers_raw.split("\n") if l.strip()]
        if not isinstance(lecturers_raw, list):
            lecturers_raw = []

        dates_rooms = (
            item.get("dates_rooms") or
            item.get("datesRooms") or
            item.get("schedule") or
            item.get("jadwal") or
            item.get("times") or
            []
        )
        if isinstance(dates_rooms, str):
            dates_rooms = [s.strip() for s in dates_rooms.split("<br/>") if s.strip()]

        schedule_items = []
        for entry in dates_rooms:
            if isinstance(entry, dict):
                day = (
                    entry.get("day") or
                    entry.get("hari") or
                    entry.get("dayName", "")
                )
                start = (
                    entry.get("start") or
                    entry.get("startTime") or
                    entry.get("start_time") or
                    entry.get("jamMulai") or
                    entry.get("waktuMulai") or
                    entry.get("begin", "")
                )
                end = (
                    entry.get("end") or
                    entry.get("endTime") or
                    entry.get("end_time") or
                    entry.get("jamSelesai") or
                    entry.get("waktuSelesai") or
                    entry.get("finish", "")
                )
                room = (
                    entry.get("room") or
                    entry.get("ruang") or
                    entry.get("location") or
                    entry.get("tempat") or
                    entry.get("ruangan", "")
                )
                schedule_items.append({
                    "day": day,
                    "start": str(start).replace(".", ":"),
                    "end": str(end).replace(".", ":"),
                    "room": room,
                })
            elif isinstance(entry, str):
                day = ""
                time_text = entry.strip()
                room = ""

                room_match = re.search(r"\(([^)]+)\)\s*$", time_text)
                if room_match:
                    room = room_match.group(1).strip()
                    time_text = time_text[:room_match.start()].strip()
                else:
                    room_match = re.search(r"\((.*)\)", time_text)
                    if room_match:
                        room = room_match.group(1).strip()
                        time_text = re.sub(r"\s*\([^)]*\)\s*", " ", time_text).strip()

                if "," in time_text:
                    parts = time_text.split(",", 1)
                    day = parts[0].strip()
                    time_text = parts[1].strip()

                time_match = re.search(r"(\d{1,2}[:.]?\d{2})\s*[-–]\s*(\d{1,2}[:.]?\d{2})", time_text)
                start = time_match.group(1).replace(".", ":") if time_match else ""
                end = time_match.group(2).replace(".", ":") if time_match else ""

                schedule_items.append({
                    "day": day,
                    "start": start,
                    "end": end,
                    "room": room,
                })

        lecturer_list = [l.strip().lstrip("- ").strip() for l in lecturers_raw if l.strip()]
        if lecturer_list and lecturer_list[0].startswith("[") and lecturer_list[0].endswith("]"):
            lecturer_list = []

        existing_class_names = {c["name"] for c in courses_map[course_key]["classes"]}
        if class_name not in existing_class_names:
            courses_map[course_key]["classes"].append({
                "name": class_name,
                "schedule_items": schedule_items,
                "lecturer": [l for l in lecturer_list if l and l != class_name],
            })

    return list(courses_map.values())

def parse_slcm_courses(html_content):
    """Parse course data from SLCM API JSON response or HTML."""
    if isinstance(html_content, str) and html_content.strip():
        first_char = html_content.strip()[0]
        if first_char in ("{", "["):
            try:
                data = json.loads(html_content)
                return _parse_v1_api_response(data)
            except (json.JSONDecodeError, Exception):
                pass

    soup = BeautifulSoup(html_content, "html.parser")
    tbody = soup.find("tbody")
    if tbody is None:
        return []

    courses = []
    current_course = None

    for tr in tbody.find_all("tr"):
        classes = _normalize_class_list(tr.get("class"))

        if "group-header-row" in classes:
            if current_course is not None and current_course.get("classes"):
                courses.append(current_course)

            strong_tag = tr.find("strong")
            header_text = strong_tag.text.strip() if strong_tag else ""
            course_code = ""
            course_name = ""

            if " - " in header_text:
                code, name = header_text.split(" - ", 1)
                course_code = code.strip()
                course_name = name.strip()
            else:
                course_code = header_text
                sibling_text = strong_tag.next_sibling if strong_tag else None
                if sibling_text:
                    course_name = str(sibling_text).strip().lstrip("-").strip()

            sks_match = re.search(r"\((\d+)\s*SKS", tr.text, re.I)
            credit = int(sks_match.group(1)) if sks_match else 0
            term_match = re.search(r"Term\s*(\d+)", tr.text, re.I)
            term = int(term_match.group(1)) if term_match else 0
            curriculum_match = re.search(r"Kurikulum\s*([\d,.-]+)", tr.text, re.I)
            curriculum = curriculum_match.group(1) if curriculum_match else ""

            current_course = {
                "course_code": course_code,
                "curriculum": curriculum,
                "name": course_name,
                "category": "",
                "credit": credit,
                "term": term,
                "classes": [],
            }

        elif "class-row" in classes and current_course is not None:
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue

            class_name = tds[1].get_text(strip=True)
            schedule_items = []
            lecturers = []

            if len(tds) >= 6:
                jadwal_cells = [li.get_text(strip=True) for li in tds[4].find_all("li")]
                if not jadwal_cells:
                    jadwal_cells = [text.strip() for text in tds[4].stripped_strings]

                lecturers = [li.get_text(strip=True) for li in tds[5].find_all("li")]
                if not lecturers:
                    lecturers = [text.strip() for text in tds[5].stripped_strings]

                for jadwal_text in jadwal_cells:
                    room = ""
                    jadwal_text = jadwal_text.strip()
                    room_match = re.match(r"^(.*)\((.*)\)\s*$", jadwal_text)
                    if room_match:
                        jadwal_text = room_match.group(1).strip()
                        room = room_match.group(2).strip()

                    day = ""
                    time_text = jadwal_text
                    if "," in jadwal_text:
                        parts = jadwal_text.split(",", 1)
                        day = parts[0].strip()
                        time_text = parts[1].strip()

                    time_match = re.search(r"(\d{1,2}[:.]?\d{2})\s*[-–]\s*(\d{1,2}[:.]?\d{2})", time_text)
                    start = time_match.group(1).replace(".", ":") if time_match else ""
                    end = time_match.group(2).replace(".", ":") if time_match else ""

                    schedule_items.append({
                        "day": day,
                        "start": start,
                        "end": end,
                        "room": room,
                    })

            current_course["classes"].append({
                "name": class_name,
                "schedule_items": schedule_items,
                "lecturer": [lect.strip().lstrip("- ").strip() for lect in lecturers if lect.strip()],
            })

    if current_course is not None and current_course.get("classes"):
        courses.append(current_course)

    return courses

def build_course_objects(parsed_courses):
    from models.period import Course, Class, ScheduleItem

    courses = []
    for raw_course in parsed_courses:
        classes = []
        for raw_class in raw_course.get("classes", []):
            schedule_items = []
            for raw_item in raw_class.get("schedule_items", []):
                schedule_items.append(ScheduleItem(
                    day=raw_item.get("day", ""),
                    start=raw_item.get("start", ""),
                    end=raw_item.get("end", ""),
                    room=raw_item.get("room", "")
                ))
            classes.append(Class(
                name=raw_class.get("name", ""),
                schedule_items=schedule_items,
                lecturer=raw_class.get("lecturer", []),
            ))

        credit = raw_course.get("credit")
        term = raw_course.get("term")
        try:
            credit = int(credit)
        except (TypeError, ValueError):
            credit = 0
        try:
            term = int(term)
        except (TypeError, ValueError):
            term = 0

        courses.append(Course(
            course_code=raw_course.get("course_code", ""),
            curriculum=raw_course.get("curriculum", ""),
            name=raw_course.get("name", ""),
            category=raw_course.get("category", ""),
            description="",
            prerequisite="",
            credit=credit,
            term=term,
            classes=classes,
        ))

    return courses
