import json
import os
import time
from urllib.parse import urlparse, parse_qs

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    sync_playwright = None
    PlaywrightTimeout = Exception


CAPTURE_URL_PATTERN = "/akademik/api/v1/class/table"


def render_with_playwright(url: str, username: str, password: str,
                           year: str = None, term: str = None, timeout: int = 120):
    """Use Playwright to login via Keycloak SSO and capture the SLCM API response.

    Flow:
      1. Navigate to the schedule page (redirects to Keycloak login)
      2. Fill the Keycloak login form and submit
      3. Wait for redirect back to the SLCM Nuxt app
      4. Extract Bearer token from API request headers and x-app-token from localStorage
      5. Call /class/table with type=group (returns ALL courses for the user's org)
      6. Return the JSON data as a string

    Returns JSON string on success, or None on failure / missing Playwright.
    """
    if sync_playwright is None:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="id-ID",
            )
            page = context.new_page()

            captured = {"auth": None, "year": None, "term": None}

            def handle_request(request):
                try:
                    url = request.url
                    if "/akademik/api/" in url:
                        h = dict(request.headers)
                        auth = h.get("authorization", "")
                        if auth:
                            captured["auth"] = auth
                    # Extract year/term from the page's own API calls
                    if "/akademik/api/v1/class/table" in url:
                        parsed = urlparse(url)
                        qs = parse_qs(parsed.query)
                        if "year" in qs:
                            captured["year"] = qs["year"][0]
                        if "term" in qs:
                            captured["term"] = qs["term"][0]
                except Exception:
                    pass

            page.on("request", handle_request)

            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")

            try:
                pwd_input = page.wait_for_selector(
                    'input[type="password"]',
                    timeout=20000
                )
            except (PlaywrightTimeout, Exception):
                pwd_input = None

            if pwd_input:
                uname_selectors = [
                    'input[name="username"]',
                    'input[id="username"]',
                    'input[type="text"]',
                    'input[name*=user]',
                ]
                username_filled = False
                for sel in uname_selectors:
                    try:
                        inp = page.query_selector(sel)
                        if inp:
                            inp.fill(username)
                            username_filled = True
                            break
                    except Exception:
                        continue

                if not username_filled:
                    all_text_inputs = page.query_selector_all('input:not([type="hidden"]):not([type="password"]):not([type="submit"])')
                    for inp in all_text_inputs:
                        try:
                            inp.fill(username)
                            break
                        except Exception:
                            continue

                try:
                    pwd_input.fill(password)
                except Exception:
                    pass

                try:
                    submit_btn = page.query_selector('input[type="submit"]')
                    if submit_btn:
                        submit_btn.click()
                    else:
                        page.keyboard.press("Enter")
                except Exception:
                    page.keyboard.press("Enter")

            try:
                page.wait_for_url("**/akademik/**", timeout=30000)
            except (PlaywrightTimeout, Exception):
                pass

            # Wait for the SPA to fully load and make API calls
            try:
                page.wait_for_load_state("networkidle", timeout=60000)
            except (PlaywrightTimeout, Exception):
                pass

            # Extract tokens
            xapp_token = page.evaluate("() => localStorage.getItem('xAppToken')")
            auth_token = captured.get("auth")

            if not auth_token or not xapp_token:
                # Try falling back to waiting more
                try:
                    page.wait_for_timeout(5000)
                except Exception:
                    pass
                xapp_token = page.evaluate("() => localStorage.getItem('xAppToken')")
                auth_token = captured.get("auth")

            if auth_token and xapp_token:
                # Use year/term from caller, intercepted API call, or fallback
                if not year:
                    year = captured.get("year")
                if not term:
                    term = captured.get("term")
                if not year:
                    year = "2026"
                if not term:
                    term = "1"

                # Build the API URL with type=group (returns all courses)
                api_url = f"/akademik/api/v1/class/table?type=group&lang=id&year={year}&term={term}"

                result_json = page.evaluate("""
                    async (params) => {
                        try {
                            const resp = await fetch(params.url, {
                                headers: {
                                    'Authorization': params.auth,
                                    'x-app-token': params.xapp,
                                    'Content-Type': 'application/json'
                                }
                            });
                            if (!resp.ok) return JSON.stringify({error: 'HTTP ' + resp.status});
                            const data = await resp.json();
                            return JSON.stringify(data);
                        } catch(e) {
                            return JSON.stringify({error: e.message});
                        }
                    }
                """, {"url": api_url, "auth": auth_token, "xapp": xapp_token})

                result_data = json.loads(result_json)
                if "error" not in result_data:
                    out_str = json.dumps(result_data, ensure_ascii=False)

                    try:
                        save_dir = os.path.dirname(os.path.abspath(__file__))
                        with open(os.path.join(save_dir, "capture_latest.json"), "w", encoding="utf-8") as f:
                            f.write(out_str)
                    except Exception:
                        pass

                    try:
                        context.close()
                        browser.close()
                    except Exception:
                        pass
                    return out_str

            # Fallback: check for HTML schedule content
            content = page.content()
            try:
                save_dir = os.path.dirname(os.path.abspath(__file__))
                with open(os.path.join(save_dir, "capture_latest.html"), "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception:
                pass

            has_schedule = "group-header-row" in content or "class-row" in content or "<tbody" in content
            if has_schedule:
                try:
                    context.close()
                    browser.close()
                except Exception:
                    pass
                return content

            try:
                context.close()
                browser.close()
            except Exception:
                pass
            return None
    except Exception:
        return None
