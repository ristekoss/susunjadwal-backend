import json
import os
import re
import requests

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

def generate_desc_prerequisite(period, username, password):
    req = requests.Session()
    r = req.post(AUTH_URL, data={'u': username,
                                    'p': password}, verify=False)
    r = req.get(CHANGEROLE_URL)
    for course in period.courses:
        code = course.course_code
        curr = course.curriculum
        if code == "" or curr == "":
            course.description = ""
            course.prerequisite = ""
            continue
        r = req.get(DETAIL_COURSES_URL.format(course=code, curr=curr)).text
        soup = BeautifulSoup(r, 'html.parser')
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
        if len(components) > 1:
            components = components[1].find_all('tr')
            
            for component in components:
                p = re.search('([A-Z]{4}[0-9]{6})', component.text)
                if p:
                    component_course_name = component.find_all('td')[2]
                    prerequisites += component_course_name.text.strip() + ","
        course.description = desc
        course.prerequisite = prerequisites[:-1]
    period.save()

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
                # Remove possible tags
                rooms[0] = rooms[0].replace('<td>', '')
                rooms[0] = rooms[0].replace('<td class="ce">', '')
                rooms[0] = rooms[0].replace('<td class="ce inf">', '')
                rooms[-1] = rooms[-1].replace('</td>', '')

                lecturers = str(sib.contents[13]).split('<br/>')

                # Cover special case in term 2022/1
                if len(lecturers) > 1 and "sampai" in lecturers[-1]:
                    lecturers = [' '.join(lecturers)]
                lecturers[0] = lecturers[0].replace('<td>', '')
                lecturers[0] = lecturers[0].replace('<td class="ce">', '')
                lecturers[0] = lecturers[0].replace('<td class="ce inf">', '')
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
