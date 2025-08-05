"""
Refactored SIAK NG scraper functions for integration with the main backend.
This module contains the core scraping logic separated from the main.py
"""
from urllib3 import poolmanager
from bs4 import BeautifulSoup
import requests
import ssl
import time
import re
import json


class TLSAdapter(requests.adapters.HTTPAdapter):
    """
    This adapter forces the use of older, more compatible SSL/TLS ciphers.
    The academic website's server may not support the latest security protocols,
    and this is crucial for establishing a successful connection.
    """
    def init_poolmanager(self, connections, maxsize, block=False):
        '''Create and initialize the urllib3 PoolManager.'''
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections, 
            maxsize=maxsize, 
            block=block, 
            ssl_version=ssl.PROTOCOL_TLS, 
            ssl_context=ctx
        )


def pre_request():
    """The server needs at least 1.2 second delay between requests"""
    delay_time = 2 # up to 2 seconds
    time.sleep(delay_time)


def format_sse(data, event=None):
    """Formats a dictionary as a Server-Sent Event string."""
    payload = f"data: {json.dumps(data)}\n"
    if event:
        payload = f"event: {event}\n{payload}"
    return payload + "\n"


def login(session, username, password):
    """
    Performs the login and role change sequence.
    This function is robust and handles the necessary steps to authenticate into SIAK NG.
    """
    BASE_URL = "https://academic.ui.ac.id"
    AUTH_URL = f"{BASE_URL}/main/Authentication/Index"
    CHANGEROLE_URL = f"{BASE_URL}/main/Authentication/ChangeRole"
    
    try:
        yield format_sse({
            "type": "status", "message": f"Authenticating as {username}..."
        }, event='log')
        
        # 1. Login to the authentication page using username and password
        pre_request()
        res = session.post(AUTH_URL, data={
            "u": username,
            "p": password
        }, headers={
            "Content-Type": "application/x-www-form-urlencoded"
        })

        if not res.status_code == 200 or "Login Failed" in res.text:
            raise Exception("Login credentials failed.")
        
        yield format_sse({
            "type": "status", "message": "Changing user role...", 
        }, event='log')

        # 2. Change role
        pre_request()
        res = session.get(CHANGEROLE_URL)
        if not res.ok or "Waspada terhadap pencurian password!" in res.text:
            raise Exception("Role change page did not contain expected text.")
        
        yield format_sse({
            "type": "status", "message": "Login successful.", 
        }, event='log')

        return True

    except requests.exceptions.RequestException as e:
        yield format_sse({
            "type": "error", "message": f"Login failed due to a network error: {e}",
        }, event='log')
        return False
    
    except Exception as e:
        yield format_sse({
            "type": "error", "message": f"Login failed: {e}",
        }, event='log')
        return False


def extract_courses(html_content):
    """
    Parses the HTML of the schedule page to extract course details.
    """
    soup = BeautifulSoup(html_content, 'lxml')
    courses = []

    # Find all courses headers
    course_headers = soup.find_all('th', class_='sub border2 pad2')

    if not course_headers:
        return []
    
    for header in course_headers:
        try:
            course_name = header.strong.text.strip()

            # Use regex to find the SKS and Term
            sks_term_match = re.search(r'(\d+)\s*SKS,\s*Term\s*(\d+)', header.text)
            credit, term = sks_term_match.groups() if sks_term_match else ('N/A', 'N/A')

            # Extract the course code and curriculum
            course_code_match = re.search(r'([A-Z]{4}\d{6})', header.text)
            course_code = course_code_match.group(1) if course_code_match else 'N/A'

            curriculum_match = re.search(r'Kurikulum\s*([\d,.-]+)', header.text)
            curriculum = curriculum_match.group(1) if curriculum_match else 'N/A'

            course_data = {
                "name": course_name,
                "credit": credit,
                "term": term,
                "course_code": course_code,
                "curriculum": curriculum,
                "classes": []
            }

            # Find all sibling 'tr' elements that represent class sections for this course
            for sibling in header.parent.find_next_siblings('tr'):
                # The class sections end when a row doesn't have a class or a new course starts
                if not sibling.get('class') or sibling.find('th', class_='sub border2 pad2'):
                    break

                # Extract class details
                cells = sibling.find_all('td')
                if len(cells) >= 7: # Check for a valid class row
                    class_name = cells[1].a.text.strip() if cells[1].a else 'N/A'
                    
                    # The schedule, room, and lecturer info is complex and contains <br> tags
                    schedule_text = cells[4].decode_contents().strip().replace('<br/>', '\n')
                    room_text = cells[5].decode_contents().strip().replace('<br/>', '\n')
                    lecturer_text = cells[6].decode_contents().strip().replace('<br/>', '\n')

                    course_data["classes"].append({
                        "class_name": class_name,
                        "schedule": schedule_text,
                        "rooms": room_text,
                        "lecturers": lecturer_text,
                    })
            courses.append(course_data)

        except:
            continue

    return courses


def scrape_siak_ng_courses(username, password):
    """
    Main function to scrape courses from SIAK NG.
    This is a generator function that yields SSE events and final result.
    """
    BASE_URL = "https://academic.ui.ac.id"
    SCHEDULE_PAGE_URL = f"{BASE_URL}/main/Schedule/Index"
    
    session = requests.Session()
    session.mount('https://', TLSAdapter())

    # Login to the SIAK NG system
    login_successful = False
    login_generator = login(session, username, password)
    for log_event in login_generator:
        # Check if this log event indicates success
        try:
            log_data = json.loads(log_event.split("data: ")[1])
            if log_data.get("message") == "Login successful.":
                login_successful = True
        except (IndexError, json.JSONDecodeError):
            pass # Not a data event, or malformed, just yield it
        yield log_event # Pass the log event to the frontend

    if not login_successful:
        yield format_sse({
            "type": "error", "message": "Login failed. Please check your credentials."
        }, event='log')
        return
    
    try:
        # Dynamically find the latest period
        yield format_sse({
            "type": "status", "message": "Accessing schedule page to find available periods."
        }, event='log')
        pre_request()
        initial_response = session.get(SCHEDULE_PAGE_URL)
        initial_response.raise_for_status()

        soup = BeautifulSoup(initial_response.text, 'lxml')

        # Find the period dropdown menu within the 'toolbar'
        toolbar = soup.find('div', class_='toolbar')
        if not toolbar:
            yield format_sse({
                "type": "error", "message": "Could not find the 'toolbar' div. Page structure may have changed."
            }, event='log')
            return
        
        period_select = toolbar.find('select', {'name': 'period'})
        if not period_select:
            yield format_sse({
                "type": "error", "message": "Could not find the period dropdown in the toolbar. Halting."
            }, event='log')
            return
            
        # Find the first option that has a real value (is not disabled)
        first_option = period_select.find('option', value=lambda v: v and v.strip())
        if not first_option:
            yield format_sse({
                "type": "error", "message": "Could not find any valid period option. Halting."
            }, event='log')
            return
        
        target_period = first_option['value']
        yield format_sse({
            "type": "status", 
            "message": f"Found latest available period: {target_period} ({first_option.text.strip()})"
        }, event='log')

        # Fetch the schedule for the found period
        yield format_sse({
            "type": "status", 
            "message": f"Fetching schedule for period: {target_period}"
        }, event='log')
        
        pre_request()
        schedule_response = session.get(SCHEDULE_PAGE_URL, params={'period': target_period})
        schedule_response.raise_for_status()

        # Extract courses from the schedule page
        courses = extract_courses(schedule_response.text)

        if courses:
            yield format_sse({
                "type": "success", 
                "message": f"Successfully extracted {len(courses)} courses for period {target_period}."
            }, event='log')
            yield format_sse({
                "type": "success", 
                "message": f"Successfully extracted {len(courses)} courses."
            }, event='log')
            yield format_sse({
                "courses": courses,
                "period": target_period,
                "period_name": first_option.text.strip()
            }, event='result')
        else:
            raise Exception("No courses found for the selected period.")

    except requests.exceptions.RequestException as e:
        yield format_sse({
            "type": "error", 
            "message": f"An error occurred while accessing the schedule page: {e}"
        }, event='log')

    except Exception as e:
        yield format_sse({
            "type": "error", 
            "message": f"An unexpected error occurred: {e}"
        }, event='log')
