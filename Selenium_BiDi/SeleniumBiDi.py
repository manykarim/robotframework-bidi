# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
"""SeleniumLibrary BiDi plugin — a thin adapter over :mod:`bidi_core`.

Keyword names mirror the Browser-BiDi adapter so suites stay portable between
the two libraries. The BiDi session attaches to the *same* browser Selenium is
driving via the driver's ``webSocketUrl`` capability (enable BiDi when opening
the browser). Correlation uses the Selenium window handle (a CDP target id on
Chrome/chromedriver) with a URL fallback (e.g. Firefox).
"""

from __future__ import annotations

import atexit
from typing import Any, Dict, List, Optional, Union

from assertionengine import AssertionOperator, verify_assertion
from robot.api import logger

from SeleniumLibrary.base import LibraryComponent, keyword

from bidi_core.adapter import PageRef
from bidi_core.manager import BiDiManager


def _as_event_list(events: Union[str, List[str], None]) -> Optional[List[str]]:
    if events is None:
        return None
    if isinstance(events, str):
        return [e.strip() for e in events.split(",") if e.strip()]
    return [str(e).strip() for e in events if str(e).strip()]


class SeleniumBiDi(LibraryComponent):
    """SeleniumLibrary plugin exposing WebDriver BiDi keywords over bidi_core."""

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._manager = BiDiManager()
        atexit.register(self._safe_teardown)

    # -- HostAdapter contract --------------------------------------------

    def current_page_ref(self) -> PageRef:
        """Correlation hints from the Selenium driver.

        On Chromium the window handle equals the CDP target id (== BiDi context
        id under the mapper), so it is a reliable ``target_id``. On other engines
        (e.g. Firefox) the window handle is an opaque id that is NOT a BiDi
        context id — using it would mis-correlate and poison the cache — so we
        return only the URL and let correlation match by URL."""
        target_id = url = None
        browser = (self.driver.capabilities or {}).get("browserName", "").lower()
        is_chromium = browser in ("chrome", "chromium", "msedge", "microsoftedge", "edge")
        try:
            if is_chromium:
                target_id = self.driver.current_window_handle
        except Exception:  # noqa: BLE001
            pass
        try:
            url = self.driver.current_url
        except Exception:  # noqa: BLE001
            pass
        return {"target_id": target_id, "url": url}

    def _page_context(self, context: Optional[str]) -> str:
        if context:
            return context
        ref = self.current_page_ref()
        ctx = self._manager.context_for_page(target_id=ref.get("target_id"), url=ref.get("url"))
        if ctx is None:
            raise RuntimeError(
                "Could not correlate the current page to a BiDi context. Pass an explicit "
                "context id, or ensure Connect BiDi targets the Selenium-driven browser."
            )
        return ctx

    # -- launch + session -------------------------------------------------

    @keyword(name="Open BiDi Browser", tags=("BiDi", "Setup"))
    def open_bidi_browser(
        self, url: Optional[str] = None, browser: str = "chrome", headless: bool = True,
        executable_path: Optional[str] = None, alias: str = "bidi", no_sandbox: bool = True,
        auto_subscribe: Optional[Union[str, List[str]]] = None,
    ) -> str:
        """Open a BiDi-enabled browser, register it with SeleniumLibrary, and
        connect BiDi — all in one keyword (no helper library needed).

        The driver is registered so the normal SeleniumLibrary keywords
        (`Go To`, `Get Title`, `Close Browser`, ...) work on it. Closes via
        SeleniumLibrary's `Close Browser`/`Close All Browsers`; call
        `Disconnect BiDi` to end the BiDi session.

        | =Argument= | =Description= |
        | ``url`` | Optional URL to open after connecting. |
        | ``browser`` | ``chrome``/``chromium``/``edge`` or ``firefox``. |
        | ``headless`` | Run headless (default True). |
        | ``executable_path`` | Driver path; empty uses Selenium Manager. |
        | ``alias`` | SeleniumLibrary driver alias. |
        | ``no_sandbox`` | Add ``--no-sandbox`` (Chromium, containers/CI). |

        Example:
        | `Open BiDi Browser` | https://example.com/ | browser=chrome |
        | `BiDi Subscribe` | log.entryAdded |
        | `Get BiDi JS Error Count` | == | ${0} |
        """
        driver = self._create_bidi_driver(browser, bool(headless),
                                          executable_path or None, bool(no_sandbox))
        self.ctx.register_driver(driver, alias)
        self.connect_bidi(browser=browser, auto_subscribe=auto_subscribe)
        if url:
            self.driver.get(url)
        return alias

    def _create_bidi_driver(self, browser: str, headless: bool,
                            executable_path: Optional[str], no_sandbox: bool):
        name = browser.lower()
        if name in ("chrome", "chromium", "edge", "msedge"):
            from selenium.webdriver import Chrome, ChromeOptions
            from selenium.webdriver.chrome.service import Service
            opts = ChromeOptions()
            if headless:
                opts.add_argument("--headless=new")
            if no_sandbox:
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
            opts.enable_bidi = True  # request a BiDi webSocketUrl capability
            kwargs: Dict[str, Any] = {"options": opts}
            if executable_path:
                kwargs["service"] = Service(executable_path=executable_path)
            return Chrome(**kwargs)
        if name == "firefox":
            from selenium.webdriver import Firefox, FirefoxOptions
            from selenium.webdriver.firefox.service import Service as FxService
            opts = FirefoxOptions()
            if headless:
                opts.add_argument("-headless")
            opts.enable_bidi = True
            kwargs = {"options": opts}
            if executable_path:
                kwargs["service"] = FxService(executable_path=executable_path)
            return Firefox(**kwargs)
        raise ValueError(f"Unsupported browser '{browser}'. Use chrome/chromium/edge or firefox.")

    # -- session ----------------------------------------------------------

    @keyword(name="Connect BiDi", tags=("BiDi", "Setup"))
    def connect_bidi(
        self, bidi_url: Optional[str] = None, browser: Optional[str] = None,
        auto_subscribe: Optional[Union[str, List[str]]] = None,
    ) -> None:
        """Attach a BiDi session to the Selenium-driven browser.

        ``bidi_url`` defaults to the driver's ``webSocketUrl`` capability — enable
        BiDi when opening the browser (``options.web_socket_url = True`` /
        ``enable_bidi=True``)."""
        url = bidi_url or (self.driver.capabilities or {}).get("webSocketUrl")
        if not url:
            raise RuntimeError(
                "No BiDi endpoint found. Open the browser with BiDi enabled "
                "(Selenium options.web_socket_url=True / enable_bidi=True), or pass bidi_url."
            )
        bname = browser or (self.driver.capabilities or {}).get("browserName")
        self._manager.connect(url, browser=bname, auto_subscribe=_as_event_list(auto_subscribe))
        logger.info(f"Connected BiDi to the Selenium browser at {url}")

    @keyword(name="Disconnect BiDi", tags=("BiDi", "Teardown"))
    def disconnect_bidi(self) -> None:
        self._manager.disconnect()

    @keyword(name="BiDi Subscribe", tags=("BiDi",))
    def bidi_subscribe(self, events: Union[str, List[str]]) -> None:
        self._manager.subscribe(_as_event_list(events) or [])

    @keyword(name="BiDi Unsubscribe", tags=("BiDi",))
    def bidi_unsubscribe(self, events: Union[str, List[str]]) -> None:
        self._manager.unsubscribe(_as_event_list(events) or [])

    @keyword(name="Clear BiDi Buffers", tags=("BiDi",))
    def clear_bidi_buffers(self) -> None:
        self._manager.clear_buffers()

    @keyword(name="Get BiDi Context For Current Page", tags=("BiDi", "Correlation"))
    def get_bidi_context_for_current_page(self) -> Optional[str]:
        return self._page_context(None)

    # -- log --------------------------------------------------------------

    @keyword(name="Get BiDi Console Log", tags=("BiDi", "Log", "Getter", "Assertion"))
    def get_bidi_console_log(self, assertion_operator: Optional[AssertionOperator] = None,
                             assertion_expected: Any = None, message: Optional[str] = None,
                             *, level: Optional[str] = None, text: Optional[str] = None,
                             pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        """Console log entries filtered by ``level``, ``text`` (substring) and/or
        ``pattern`` (regex)."""
        value = self._manager.get_console_log(level=level, text=text, pattern=pattern)
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi console log", message)

    @keyword(name="Get BiDi JS Error Count", tags=("BiDi", "Log", "Getter", "Assertion"))
    def get_bidi_js_error_count(self, assertion_operator: Optional[AssertionOperator] = None,
                                assertion_expected: Any = None, message: Optional[str] = None) -> int:
        value = self._manager.get_js_error_count()
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi JS error count", message)

    @keyword(name="Get BiDi JS Errors", tags=("BiDi", "Log", "Getter", "Assertion"))
    def get_bidi_js_errors(self, assertion_operator: Optional[AssertionOperator] = None,
                           assertion_expected: Any = None, message: Optional[str] = None) -> List[Dict[str, Any]]:
        value = self._manager.get_js_errors()
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi JS errors", message)

    @keyword(name="Wait For BiDi Log Entry", tags=("BiDi", "Log"))
    def wait_for_bidi_log_entry(self, text: Optional[str] = None, level: Optional[str] = None,
                                timeout: float = 10.0) -> Dict[str, Any]:
        def matcher(entry: Dict[str, Any]) -> bool:
            if level is not None and entry.get("level") != level:
                return False
            return text is None or text in (entry.get("text") or "")
        return self._manager.wait_for_log_entry(matcher, timeout=float(timeout))

    # -- network (observe + mock) ----------------------------------------

    @keyword(name="Get BiDi Network Events", tags=("BiDi", "Network"))
    def get_bidi_network_events(self, url_glob: Optional[str] = None,
                                since: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._manager.get_network_events(url_glob=url_glob, since=since)

    @keyword(name="Get BiDi Slowest Resources", tags=("BiDi", "Network", "Performance", "Getter", "Assertion"))
    def get_bidi_slowest_resources(self, assertion_operator: Optional[AssertionOperator] = None,
                                   assertion_expected: Any = None, message: Optional[str] = None,
                                   *, top: int = 10, phase: str = "total",
                                   url_glob: Optional[str] = None) -> List[Dict[str, Any]]:
        """Top N slowest resources by a timing phase (default total), slowest first."""
        value = self._manager.get_slowest_resources(top=int(top), phase=phase, url_glob=url_glob)
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi slowest resources", message)

    @keyword(name="Get BiDi Largest Resources", tags=("BiDi", "Network", "Performance", "Getter", "Assertion"))
    def get_bidi_largest_resources(self, assertion_operator: Optional[AssertionOperator] = None,
                                   assertion_expected: Any = None, message: Optional[str] = None,
                                   *, top: int = 10, url_glob: Optional[str] = None) -> List[Dict[str, Any]]:
        """Top N largest resources by transferred size (bytes), largest first."""
        value = self._manager.get_largest_resources(top=int(top), url_glob=url_glob)
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi largest resources", message)

    @keyword(name="Get BiDi Aria Snapshot", tags=("BiDi", "Accessibility", "Getter", "Assertion"))
    def get_bidi_aria_snapshot(self, assertion_operator: Optional[AssertionOperator] = None,
                               assertion_expected: Any = None, message: Optional[str] = None,
                               *, selector: Optional[str] = None,
                               context: Optional[str] = None) -> str:
        """Playwright-style ARIA snapshot (role + accessible name tree) of the page
        or a ``selector`` subtree — assert with ``contains`` on roles/names."""
        value = self._manager.get_aria_snapshot(selector=selector, context=self._page_context(context))
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi aria snapshot", message)

    @keyword(name="Wait For BiDi Response", tags=("BiDi", "Network"))
    def wait_for_bidi_response(self, url_glob: str, timeout: float = 10.0) -> Dict[str, Any]:
        return self._manager.wait_for_response(url_glob, timeout=float(timeout))

    @keyword(name="Get BiDi Response Status", tags=("BiDi", "Network", "Getter", "Assertion"))
    def get_bidi_response_status(self, url_glob: str, assertion_operator: Optional[AssertionOperator] = None,
                                 assertion_expected: Any = None, message: Optional[str] = None) -> int:
        value = self._manager.get_response_status(url_glob)
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi response status", message)

    @keyword(name="Get BiDi Response Body", tags=("BiDi", "Network", "Getter", "Assertion"))
    def get_bidi_response_body(self, request_id: str, assertion_operator: Optional[AssertionOperator] = None,
                               assertion_expected: Any = None, message: Optional[str] = None) -> str:
        value = self._manager.get_response_body(request_id)
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi response body", message)

    @keyword(name="BiDi Mock Response", tags=("BiDi", "Network", "Intercept"))
    def bidi_mock_response(self, url_glob: str, status: int = 200, body: Optional[str] = None,
                           headers: Optional[Dict[str, str]] = None) -> None:
        self._manager.add_mock(url_glob, status=int(status), headers=headers, body=body)

    @keyword(name="BiDi Fail Request", tags=("BiDi", "Network", "Intercept"))
    def bidi_fail_request(self, url_glob: str) -> None:
        self._manager.add_fault(url_glob)

    @keyword(name="Clear BiDi Intercepts", tags=("BiDi", "Network", "Intercept"))
    def clear_bidi_intercepts(self) -> None:
        self._manager.clear_intercepts()

    # -- script & page ----------------------------------------------------

    @keyword(name="BiDi Evaluate", tags=("BiDi", "Script", "Getter", "Assertion"))
    def bidi_evaluate(self, expression: str, assertion_operator: Optional[AssertionOperator] = None,
                      assertion_expected: Any = None, message: Optional[str] = None,
                      *, context: Optional[str] = None) -> Any:
        value = self._manager.evaluate(expression, context=self._page_context(context))
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi evaluate", message)

    @keyword(name="Get BiDi Url", tags=("BiDi", "PageContent", "Getter", "Assertion"))
    def get_bidi_url(self, assertion_operator: Optional[AssertionOperator] = None,
                     assertion_expected: Any = None, message: Optional[str] = None,
                     *, context: Optional[str] = None) -> str:
        value = self._manager.get_url(context=self._page_context(context))
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi URL", message)

    @keyword(name="Get BiDi Title", tags=("BiDi", "PageContent", "Getter", "Assertion"))
    def get_bidi_title(self, assertion_operator: Optional[AssertionOperator] = None,
                       assertion_expected: Any = None, message: Optional[str] = None,
                       *, context: Optional[str] = None) -> str:
        value = self._manager.get_title(context=self._page_context(context))
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi title", message)

    @keyword(name="Get BiDi Element Count", tags=("BiDi", "DOM", "Getter", "Assertion"))
    def get_bidi_element_count(self, strategy: str, value: str,
                               assertion_operator: Optional[AssertionOperator] = None,
                               assertion_expected: Any = None, message: Optional[str] = None,
                               *, context: Optional[str] = None, pierce_shadow: bool = False) -> int:
        count = self._manager.get_element_count(strategy, value, context=self._page_context(context),
                                                pierce_shadow=pierce_shadow)
        return verify_assertion(count, assertion_operator, assertion_expected, "BiDi element count", message)

    # -- emulation & isolation -------------------------------------------

    @keyword(name="BiDi Set Locale", tags=("BiDi", "Emulation"))
    def bidi_set_locale(self, locale: Optional[str] = None, context: Optional[str] = None) -> None:
        self._manager.set_locale(locale or None, context=self._page_context(context))

    @keyword(name="BiDi Set Timezone", tags=("BiDi", "Emulation"))
    def bidi_set_timezone(self, timezone: Optional[str] = None, context: Optional[str] = None) -> None:
        self._manager.set_timezone(timezone or None, context=self._page_context(context))

    @keyword(name="New BiDi User Context", tags=("BiDi", "Isolation", "Setup"))
    def new_bidi_user_context(self) -> str:
        return self._manager.create_user_context()

    @keyword(name="Remove BiDi User Context", tags=("BiDi", "Isolation", "Teardown"))
    def remove_bidi_user_context(self, user_context: str) -> None:
        self._manager.remove_user_context(user_context)

    # -- internal ---------------------------------------------------------

    def _safe_teardown(self) -> None:
        try:
            self._manager.disconnect()
        except Exception:  # noqa: BLE001
            pass
