import json
import os
import re
import requests
import datetime

from bs4 import BeautifulSoup
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from models.period import (
    Class,
    Course,
    Period,
    ScheduleItem
)


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


BASE_URL = "https://academic.ui.ac.id/main"
AUTH_URL = f"{BASE_URL}/Authentication/Index"
CHANGEROLE_URL = f"{BASE_URL}/Authentication/ChangeRole"
DETAIL_SCHEDULE_URL = f"{BASE_URL}/Schedule/Index?period={{period}}&search="
GENERAL_SCHEDULE_URL = f"{BASE_URL}/Schedule/IndexOthers?fac={{fac}}&org={{org}}&per={{period}}&search="
DETAIL_COURSES_URL = f"{BASE_URL}/Course/Detail?course={{course}}&curr={{curr}}"
DEFAULT_CREDENTIAL = "01.00.12.01"

def scrape_courses_with_credentials(period, username, password):
    req = requests.Session()
    r = req.post(AUTH_URL, data={'u': username,
                                 'p': password}, verify=False)
    r = req.get(CHANGEROLE_URL)
    r = req.get(DETAIL_SCHEDULE_URL.format(period=period))
    courses = create_courses(r.text, is_detail=True)
    generate_desc_prerequisite(courses, req)
    return courses


def scrape_courses(major_kd_org, period, skip_not_detail=False):
    username, password = fetch_credential(major_kd_org)
    if (username is not None) and (password is not None):
        req = requests.Session()
        r = req.post(AUTH_URL, data={'u': username,
                                     'p': password}, verify=False)
        r = req.get(CHANGEROLE_URL)
        r = req.get(DETAIL_SCHEDULE_URL.format(period=period))
        courses = create_courses(r.text, is_detail=True)
        return courses, True

    if not skip_not_detail:
        username, password = fetch_credential(DEFAULT_CREDENTIAL)
        fac, org = parse_kd_org(major_kd_org)
        req = requests.Session()
        r = req.post(AUTH_URL, data={'u': username,
                                     'p': password}, verify=False)
        r = req.get(CHANGEROLE_URL)
        r = req.get(GENERAL_SCHEDULE_URL.format(
            fac=fac, org=org, period=period))
        courses = create_courses(r.text)
        return courses, False

    return None, None


def fetch_credential(major_kd_org):
    path = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(path, "credentials.json")

    with open(filename, "r") as fd:
        credentials = json.loads(fd.read())
        val = credentials.get(major_kd_org, {})
        return (val.get("username"), val.get("password"))


def parse_kd_org(kd_org):
    return kd_org[-5:], kd_org


def get_period_and_kd_org(html):
    try:
        soup = BeautifulSoup(html, 'html.parser')

        item = soup.find(class_="linfo", style="border-left:0")
        m = re.search(r"\((\d\d.\d\d.\d\d.\d\d)\)", item.text)
        kd_org = m[1]

        item = soup.find('option', selected=True)
        period = item["value"]

        return period, kd_org

    except:
        pass

    return None, None

def generate_desc_prerequisite(courses, req):
    print("=== generating desc and prereq ===")
    now = datetime.datetime.now()
    for course in courses:
        html = req.get(DETAIL_COURSES_URL.format(course=course.course_code, curr=course.curriculum)).text
        soup = BeautifulSoup(html, 'html.parser')
        for textarea in soup.findAll('textarea'):
            if textarea.contents:
                textarea_content = textarea.contents[0]
                desc = textarea_content.replace('\r\n', ' ')
                if len(desc) > 2048:
                    desc = ""
            else:
                desc = ""
            break
        components = soup.find(text="Prasyarat Mata Kuliah").parent.findNextSibling('td').contents
        prerequisites = ""
        for component in components:
            p = re.search('([A-Z]{4}[0-9]{6})', str(component))
            if p:
                prerequisites += p.group().strip() + ","
        course.description = desc
        course.prerequisite = prerequisites[:-1]
    end = datetime.datetime.now()
    print("time elapsed ms :: "+ str((end-now).microseconds))
    print("time elapsed s :: "+ str((end-now).seconds))

def create_courses(html, is_detail=False):
    soup = BeautifulSoup(html, 'html.parser')
    if is_detail:
        classes = soup.find_all('th', class_='sub border2 pad2')
    else:
        classes = soup.find_all('th', class_='sub border2 pad1')

    courses = []
    for class_ in classes:
        course_name = class_.strong.text
        m = re.search('([0-9]+) SKS, Term ([0-9]+)', class_.text)
        if m:
            credit, term = m.group().split(' SKS, Term ')

        c = re.search('([A-Z]{4}[0-9]{6}) -', class_.text)
        course_code = c.group()[:-2] if c else ''

        c = re.search('Kurikulum ([0-9,.,-]+)', class_.text)
        curriculum = c.group()[10:] if c else ''

        classes = []
        for sib in class_.parent.find_next_siblings('tr'):
            if (sib.get('class') == None):
                break

            class_name = sib.a.text
            try:
                schedules = str(sib.contents[9]).split('<br/>')
                schedules[0] = schedules[0].replace(
                    '<td nowrap="">', '')
                schedules[-1] = schedules[-1].replace('</td>', '')

                rooms = str(sib.contents[11]).split('<br/>')
                if is_detail:
                    rooms[0] = rooms[0].replace('<td>', '')
                else:
                    rooms[0] = rooms[0].replace('<td class="ce">', '')
                rooms[-1] = rooms[-1].replace('</td>', '')

                lecturers = str(sib.contents[13]).split('<br/>')
                lecturers[0] = lecturers[0].replace('<td>', '')
                lecturers[-1] = lecturers[-1].replace('</td>', '')
                lecturers = [l.lstrip('-') for l in lecturers]

                result = []
                schedules = zip(schedules, rooms)
                for schedule, room in schedules:
                    day, time = schedule.split(', ')
                    start, end = time.split('-')
                    result.append(ScheduleItem(
                        day=day,
                        start=start,
                        end=end,
                        room=room
                    ))

                classes.append(Class(
                    name=class_name,
                    schedule_items=result,
                    lecturer=lecturers
                ))

            except (IndexError, ValueError) as e:
                pass

        if classes:
            courses.append(Course(
                name=course_name,
                credit=credit,
                term=term,
                classes=classes,
                course_code=course_code,
                curriculum=curriculum
            ))

    return courses
