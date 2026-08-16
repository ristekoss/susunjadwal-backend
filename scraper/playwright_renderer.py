import json
import os
import logging
import time
import traceback
from urllib.parse import urlparse, parse_qs

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    sync_playwright = None
    PlaywrightTimeout = Exception


CAPTURE_URL_PATTERN = "/akademik/api/v1/class/table"


logger = logging.getLogger(__name__)


def _debug(message: str):
    logger.info(message)
    print(message)


def _debug_exception(message: str):
    error_text = traceback.format_exc()
    logger.error("%s\n%s", message, error_text)
    print(f"{message}\n{error_text}")


def render_with_playwright(url: str, username: str, password: str,
                           year: str = None, term: str = None, timeout: int = 120):
    """Use Playwright to login via Keycloak SSO and capture the SLCM API response.

    Flow:
      1. Navigate to the schedule page (redirects to Keycloak login)
      2. Fill the Keycloak login form and submit
      3. Wait for redirect back to the SLCM Nuxt app
      4. Extract Bearer token from API request headers and x-app-token from localStorage
      5. Call /class/table for each class category (type=internal, type=group, type=external)
      6. Merge all responses and return the combined JSON data as a string

    Returns JSON string on success, or None on failure / missing Playwright.
    """
    if sync_playwright is None:
        _debug("[PLAYWRIGHT] Playwright is not installed; skipping browser capture")
        return None

    try:
        with sync_playwright() as p:
            _debug(f"[PLAYWRIGHT] Launching Playwright browser for URL: {url}")
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="id-ID",
            )
            _debug(f"[PLAYWRIGHT] Creating new page in browser context for URL: {url}")
            page = context.new_page()

            # Abort heavy/non-essential requests to prevent hanging network calls
            page.route(
                "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,otf}",
                lambda route: route.abort()
            )

            captured = {"auth": None, "year": None, "term": None}

            def handle_request(request):
                try:
                    req_url = request.url
                    if "/akademik/api/" in req_url:
                        h = dict(request.headers)
                        auth = h.get("authorization", "")
                        if auth:
                            captured["auth"] = auth
                            _debug(
                                f"[PLAYWRIGHT] Captured authorization header from request: {req_url}"
                            )
                    # Extract year/term from the page's own API calls
                    if "/akademik/api/v1/class/table" in req_url:
                        parsed = urlparse(req_url)
                        qs = parse_qs(parsed.query)
                        if "year" in qs:
                            captured["year"] = qs["year"][0]
                        if "term" in qs:
                            captured["term"] = qs["term"][0]
                except Exception:
                    _debug_exception("[PLAYWRIGHT] Request handler failed")

            _debug(f"[PLAYWRIGHT] Setting up request interception for URL: {url}")
            page.on("request", handle_request)

            _debug(f"[PLAYWRIGHT] Navigating to target page with timeout={timeout}s")
            try:
                # Use "commit" to proceed as soon as network headers arrive
                page.goto(url, timeout=timeout * 1000, wait_until="commit")
                _debug(f"[PLAYWRIGHT] Navigation committed, current URL: {page.url}")
            except (PlaywrightTimeout, Exception) as nav_err:
                _debug(f"[PLAYWRIGHT] Initial goto hit exception ({nav_err}); attempting to proceed with DOM inspection")
            _debug(f"[PLAYWRIGHT] Navigation complete, current URL: {page.url}")

            try:
                pwd_input = page.wait_for_selector(
                    'input[type="password"]', timeout=20000
                )
                _debug("[PLAYWRIGHT] Password field found")
            except (PlaywrightTimeout, Exception):
                _debug("[PLAYWRIGHT] Password field not found within 20s")
                pwd_input = None

            if pwd_input:
                uname_selectors = [
                    'input[name="username"]',
                    'input[id="username"]',
                    'input[type="text"]',
                    "input[name*=user]",
                ]
                username_filled = False
                for sel in uname_selectors:
                    try:
                        inp = page.query_selector(sel)
                        if inp:
                            inp.fill(username)
                            username_filled = True
                            _debug(
                                f"[PLAYWRIGHT] Filled username using selector: {sel}"
                            )
                            break
                    except Exception:
                        _debug_exception(
                            f"[PLAYWRIGHT] Failed filling username with selector: {sel}"
                        )
                        continue

                if not username_filled:
                    _debug(
                        "[PLAYWRIGHT] Falling back to first visible text input for username"
                    )
                    all_text_inputs = page.query_selector_all(
                        'input:not([type="hidden"]):not([type="password"]):not([type="submit"])'
                    )
                    for inp in all_text_inputs:
                        try:
                            inp.fill(username)
                            _debug(
                                "[PLAYWRIGHT] Filled username using fallback text input"
                            )
                            break
                        except Exception:
                            _debug_exception(
                                "[PLAYWRIGHT] Failed filling fallback username input"
                            )
                            continue

                try:
                    pwd_input.fill(password)
                    _debug("[PLAYWRIGHT] Filled password field")
                except Exception:
                    _debug_exception("[PLAYWRIGHT] Failed filling password field")

                try:
                    submit_btn = page.query_selector('input[type="submit"]')
                    if submit_btn:
                        submit_btn.click()
                        _debug("[PLAYWRIGHT] Submitted login form using submit button")
                    else:
                        page.keyboard.press("Enter")
                        _debug("[PLAYWRIGHT] Submitted login form using Enter key")
                except Exception:
                    _debug_exception(
                        "[PLAYWRIGHT] Failed submitting login form, falling back to Enter key"
                    )
                    page.keyboard.press("Enter")

            try:
                page.wait_for_url("**/akademik/**", timeout=30000)
                _debug(f"[PLAYWRIGHT] Detected akademik redirect: {page.url}")
            except (PlaywrightTimeout, Exception):
                _debug(
                    f"[PLAYWRIGHT] Timed out waiting for akademik redirect; current URL: {page.url}"
                )
                pass

            # Wait for the SPA to fully load and make API calls
            try:
                page.wait_for_load_state("networkidle", timeout=60000)
                _debug("[PLAYWRIGHT] Page reached network idle")
            except (PlaywrightTimeout, Exception):
                _debug(
                    f"[PLAYWRIGHT] Timed out waiting for network idle; current URL: {page.url}"
                )
                pass

            # Extract tokens
            xapp_token = page.evaluate("() => localStorage.getItem('xAppToken')")
            auth_token = captured.get("auth")
            _debug(
                "[PLAYWRIGHT] Token snapshot after initial load: "
                f"auth={'yes' if auth_token else 'no'}, xAppToken={'yes' if xapp_token else 'no'}, "
                f"year={captured.get('year')}, term={captured.get('term')}"
            )

            if not auth_token or not xapp_token:
                # Try falling back to waiting more
                try:
                    page.wait_for_timeout(5000)
                    _debug("[PLAYWRIGHT] Waiting an extra 5s for missing tokens")
                except Exception:
                    _debug_exception("[PLAYWRIGHT] Extra wait for tokens failed")
                xapp_token = page.evaluate("() => localStorage.getItem('xAppToken')")
                auth_token = captured.get("auth")
                _debug(
                    "[PLAYWRIGHT] Token snapshot after retry: "
                    f"auth={'yes' if auth_token else 'no'}, xAppToken={'yes' if xapp_token else 'no'}"
                )

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

                _debug(
                    "[PLAYWRIGHT] Using request parameters: "
                    f"year={year}, term={term}, auth_present={bool(auth_token)}, xapp_present={bool(xapp_token)}"
                )

                # Fetch every class category so internal, external, and joint
                # ("bersama") courses are all captured, not just type=group.
                # Categories match what the frontend renders (Kelas Internal /
                # Kelas External / Kelas Bersama).
                class_types = [
                    ("internal", "Kelas Internal"),
                    ("group", "Kelas Bersama"),
                    ("external", "Kelas External"),
                ]

                merged_items = []
                merged_success = False
                for type_key, category in class_types:
                    api_url = f"/akademik/api/v1/class/table?type={type_key}&lang=id&year={year}&term={term}"
                    _debug(
                        f"[PLAYWRIGHT] Fetching class table for type={type_key}, category={category}"
                    )

                    result_json = page.evaluate(
                        """
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
                    """,
                        {"url": api_url, "auth": auth_token, "xapp": xapp_token},
                    )

                    result_data = json.loads(result_json)
                    if "error" in result_data:
                        _debug(
                            f"[PLAYWRIGHT] API returned error for type={type_key}: {result_data['error']}"
                        )
                        continue

                    merged_success = True
                    items = result_data.get("data") or []
                    if not isinstance(items, list):
                        items = []
                    _debug(
                        f"[PLAYWRIGHT] Received {len(items)} items for type={type_key}"
                    )
                    for item in items:
                        if isinstance(item, dict):
                            item["category"] = category
                            merged_items.append(item)

                if merged_success:
                    out_str = json.dumps(
                        {
                            "data": merged_items,
                            "message": "Table Class is successfuly!",
                        },
                        ensure_ascii=False,
                    )

                    _debug(
                        f"[PLAYWRIGHT] Successfully merged {len(merged_items)} class items"
                    )

                    try:
                        save_dir = os.path.dirname(os.path.abspath(__file__))
                        with open(
                            os.path.join(save_dir, "capture_latest.json"),
                            "w",
                            encoding="utf-8",
                        ) as f:
                            f.write(out_str)
                        _debug("[PLAYWRIGHT] Wrote capture_latest.json")
                    except Exception:
                        _debug_exception(
                            "[PLAYWRIGHT] Failed to write capture_latest.json"
                        )

                    try:
                        context.close()
                        browser.close()
                    except Exception:
                        _debug_exception(
                            "[PLAYWRIGHT] Failed to close Playwright browser cleanly"
                        )
                    return out_str

                _debug(
                    "[PLAYWRIGHT] No class table request succeeded; falling back to page HTML inspection"
                )

            # Fallback: check for HTML schedule content
            content = page.content()
            _debug(
                f"[PLAYWRIGHT] Captured page HTML fallback content, length={len(content)}"
            )
            try:
                save_dir = os.path.dirname(os.path.abspath(__file__))
                with open(
                    os.path.join(save_dir, "capture_latest.html"), "w", encoding="utf-8"
                ) as f:
                    f.write(content)
                _debug("[PLAYWRIGHT] Wrote capture_latest.html")
            except Exception:
                _debug_exception("[PLAYWRIGHT] Failed to write capture_latest.html")

            has_schedule = (
                "group-header-row" in content
                or "class-row" in content
                or "<tbody" in content
            )
            _debug(
                f"[PLAYWRIGHT] HTML fallback schedule detection result: {has_schedule}"
            )
            if has_schedule:
                try:
                    context.close()
                    browser.close()
                except Exception:
                    _debug_exception(
                        "[PLAYWRIGHT] Failed to close browser after HTML fallback"
                    )
                return content

            try:
                context.close()
                browser.close()
            except Exception:
                _debug_exception(
                    "[PLAYWRIGHT] Failed to close browser before returning None"
                )
            _debug(
                "[PLAYWRIGHT] Returning None after exhausting all capture strategies"
            )
            return None
    except Exception:
        _debug_exception("[PLAYWRIGHT] Unhandled exception in render_with_playwright")
        return None
