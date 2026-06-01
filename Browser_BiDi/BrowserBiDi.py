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
"""Browser-BiDi: a WebDriver BiDi observability plugin for the Browser library.

Loaded as a Browser plugin::

    Library    Browser    plugins=${path}/BrowserBiDi.py

This is a thin synchronous facade over :class:`Browser_BiDi.manager.BiDiManager`
(see design.md). It opens an *independent* BiDi WebSocket to the same browser
Playwright is driving and exposes BiDi-only observability data as keywords. It
deliberately does not duplicate Playwright interaction (decision D7).
"""

from __future__ import annotations

import atexit
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from robot.api import logger
from robot.api.deco import keyword

from assertionengine import AssertionOperator, verify_assertion

from Browser.base.librarycomponent import LibraryComponent

from bidi_core.adapter import PageRef
from bidi_core.launcher import (
    launch_chromium,
    launch_chromium_driverless,
    launch_firefox,
)
from bidi_core.manager import BiDiManager


def _as_event_list(events: Union[str, List[str]]) -> List[str]:
    if isinstance(events, str):
        return [e.strip() for e in events.split(",") if e.strip()]
    return [str(e).strip() for e in events if str(e).strip()]


class BrowserBiDi(LibraryComponent):
    """Browser library plugin exposing WebDriver BiDi observability keywords."""

    def __init__(self, library, buffer_size: int = 1000) -> None:
        super().__init__(library)
        self._manager = BiDiManager(buffer_size=int(buffer_size))
        self._launched = None  # browser started by 'Launch BiDi Browser', if any
        # Bundled JS helper used purely to read Playwright-side correlation
        # metadata (CDP target id + URL).
        self.initialize_js_extension(Path(__file__).parent / "helper.js")
        # Defensive safety net: never leak a loop/socket if the suite crashes
        # before Disconnect BiDi / Close Browser teardown runs (design.md D4).
        atexit.register(self._safe_teardown)

    # -- launch keywords --------------------------------------------------

    @keyword(name="Launch BiDi Browser", tags=("BiDi", "Setup"))
    def launch_bidi_browser(
        self,
        browser: str = "chromium",
        headless: bool = True,
        no_sandbox: bool = False,
        driverless: bool = True,
    ) -> Dict[str, Any]:
        """Launch a BiDi-reachable browser and return its endpoints.

        Returns ``{bidi_url, cdp_url, transport, browser}``. Pass ``bidi_url`` /
        ``transport`` to `Connect BiDi`, and ``cdp_url`` to Browser's
        ``Connect To Browser  use_cdp=True`` for full coexistence. Driverless by
        default (Chrome via the chromium-bidi mapper; Firefox native) — no
        chromedriver/geckodriver needed. The launched browser is tracked and torn
        down on `Close BiDi Browser`, `Disconnect BiDi`, or process exit.

        | =Argument= | =Description= |
        | ``browser`` | ``chromium`` (alias chrome/edge) or ``firefox``. |
        | ``headless`` | Run headless (default True). |
        | ``no_sandbox`` | Add ``--no-sandbox`` (containers/CI). Chromium only. |
        | ``driverless`` | Use native/mapper BiDi (default True); False uses a WebDriver. |

        Example:
        | ${b}= | `Launch BiDi Browser` | chromium |
        | `Connect To Browser` | ${b}[cdp_url] | use_cdp=True |
        | `Connect BiDi` | ${b}[bidi_url] | transport=${b}[transport] |
        """
        self._close_launched()
        name = browser.lower()
        extra = ["--no-sandbox", "--disable-dev-shm-usage"] if no_sandbox else None
        if name in ("chromium", "chrome", "edge"):
            if driverless:
                launched = launch_chromium_driverless(headless=headless, extra_args=extra)
                transport = "cdp-mapper"
            else:
                launched = launch_chromium(headless=headless, extra_args=extra)
                transport = "websocket"
        elif name == "firefox":
            launched = launch_firefox(headless=headless, driverless=driverless)
            transport = "websocket"
        else:
            raise ValueError(
                f"Unsupported browser '{browser}'. Use chromium/chrome/edge or firefox."
            )
        self._launched = launched
        logger.info(
            f"Launched {name} (driverless={driverless}): bidi={launched.bidi_url} cdp={launched.cdp_url}"
        )
        return {
            "bidi_url": launched.bidi_url,
            "cdp_url": launched.cdp_url,
            "transport": transport,
            "browser": name,
        }

    @keyword(name="Close BiDi Browser", tags=("BiDi", "Teardown"))
    def close_bidi_browser(self) -> None:
        """Close a browser started by `Launch BiDi Browser` (no-op otherwise)."""
        self._close_launched()

    def _close_launched(self) -> None:
        if self._launched is not None:
            launched, self._launched = self._launched, None
            try:
                launched.close()
            except Exception:  # noqa: BLE001 - teardown is best-effort
                pass

    # -- lifecycle keywords ----------------------------------------------

    @keyword(name="Connect BiDi", tags=("BiDi", "Setup"))
    def connect_bidi(
        self,
        bidi_url: str,
        browser: Optional[str] = None,
        auto_subscribe: Optional[Union[str, List[str]]] = None,
        transport: str = "websocket",
    ) -> None:
        """Open a BiDi connection to the running browser and start a session.

        ``bidi_url`` is the BiDi endpoint. ``browser`` is an optional hint
        (``chromium``/``firefox``); WebKit/Safari is rejected. ``auto_subscribe``
        optionally subscribes to event classes at connect.

        ``transport``:
        - ``websocket`` (default): connect directly to a BiDi WebSocket
          (Firefox native, or a driver-provided ``webSocketUrl``).
        - ``cdp-mapper``: driverless Chrome — ``bidi_url`` is Chrome's CDP
          ``webSocketDebuggerUrl`` and BiDi is spoken through the bundled
          chromium-bidi mapper (no chromedriver)."""
        subscribe = _as_event_list(auto_subscribe) if auto_subscribe else None
        self._manager.connect(
            bidi_url, browser=browser, auto_subscribe=subscribe, transport=transport
        )
        logger.info(f"Connected BiDi session to {bidi_url} (transport={transport})")

    @keyword(name="Disconnect BiDi", tags=("BiDi", "Teardown"))
    def disconnect_bidi(self) -> None:
        """Unsubscribe, close the BiDi socket, and stop the background loop.

        Also closes a browser started via `Launch BiDi Browser` (browsers you
        launched yourself are left untouched)."""
        self._manager.disconnect()
        self._close_launched()

    @keyword(name="BiDi Subscribe", tags=("BiDi",))
    def bidi_subscribe(self, events: Union[str, List[str]]) -> None:
        """Subscribe to BiDi event classes, e.g.
        ``network.responseCompleted, log.entryAdded``."""
        self._manager.subscribe(_as_event_list(events))

    @keyword(name="BiDi Unsubscribe", tags=("BiDi",))
    def bidi_unsubscribe(self, events: Union[str, List[str]]) -> None:
        """Stop receiving the given BiDi event classes."""
        self._manager.unsubscribe(_as_event_list(events))

    @keyword(name="Clear BiDi Buffers", tags=("BiDi",))
    def clear_bidi_buffers(self) -> None:
        """Drop all buffered network/log events (e.g. between tests for clean counts)."""
        self._manager.clear_buffers()

    @keyword(name="Get BiDi Support Matrix", tags=("BiDi", "Getter"))
    def get_bidi_support_matrix(self) -> Dict[str, Any]:
        """Return the per-engine BiDi capability support matrix and the
        engine/spec versions it was validated against."""
        return self._manager.support_matrix()

    # -- network keywords -------------------------------------------------

    @keyword(name="Get BiDi Network Events", tags=("BiDi", "Network"))
    def get_bidi_network_events(
        self, url_glob: Optional[str] = None, since: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Return buffered network events, optionally filtered by URL glob/``since``."""
        return self._manager.get_network_events(url_glob=url_glob, since=since)

    @keyword(name="Get BiDi Response Body", tags=("BiDi", "Network", "Getter", "Assertion"))
    def get_bidi_response_body(
        self,
        request_id: str,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
    ) -> str:
        """Retrieve a completed response body by its BiDi request id.

        Optionally asserts on the body. See `Assertions` for operator details."""
        value = self._manager.get_response_body(request_id)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi response body", message
        )

    @keyword(name="Get BiDi Response Status", tags=("BiDi", "Network", "Getter", "Assertion"))
    def get_bidi_response_status(
        self,
        url_glob: str,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
    ) -> int:
        """HTTP status of the last captured response whose URL matches ``url_glob``."""
        value = self._manager.get_response_status(url_glob)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi response status", message
        )

    @keyword(name="Get BiDi Response Headers", tags=("BiDi", "Network", "Getter", "Assertion"))
    def get_bidi_response_headers(
        self,
        url_glob: str,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
    ) -> Dict[str, str]:
        """Response headers (lower-cased keys) of the last response matching ``url_glob``."""
        value = self._manager.get_response_headers(url_glob)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi response headers", message
        )

    @keyword(name="Get BiDi Network Event Count", tags=("BiDi", "Network", "Getter", "Assertion"))
    def get_bidi_network_event_count(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        url_glob: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> int:
        """Number of buffered network events, optionally filtered by URL glob / type."""
        value = self._manager.get_network_event_count(url_glob=url_glob, event_type=event_type)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi network event count", message
        )

    @keyword(name="Get BiDi Resource Timings", tags=("BiDi", "Network", "Getter", "Assertion"))
    def get_bidi_resource_timings(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        url_glob: Optional[str] = None,
        sort_by: Optional[str] = None,
        top: Optional[int] = None,
        descending: bool = True,
    ) -> List[Dict[str, Any]]:
        """Per-resource timing + size (dns/connect/tls/ttfb/download/total ms,
        size bytes, url, status, mime, from_cache). Optionally ``sort_by`` a field
        (``total``/``ttfb``/``download``/``dns``/``connect``/``tls``/``size``) and
        keep the ``top`` N."""
        value = self._manager.get_resource_timings(
            url_glob=url_glob, sort_by=sort_by,
            top=int(top) if top is not None else None, descending=descending)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi resource timings", message
        )

    @keyword(name="Get BiDi Slowest Resources", tags=("BiDi", "Network", "Performance", "Getter", "Assertion"))
    def get_bidi_slowest_resources(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        top: int = 10,
        phase: str = "total",
        url_glob: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """The ``top`` N slowest resources by a timing ``phase`` (default total
        load time), slowest first. E.g. ``Get BiDi Slowest Resources  top=10``."""
        value = self._manager.get_slowest_resources(top=int(top), phase=phase, url_glob=url_glob)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi slowest resources", message
        )

    @keyword(name="Get BiDi Largest Resources", tags=("BiDi", "Network", "Performance", "Getter", "Assertion"))
    def get_bidi_largest_resources(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        top: int = 10,
        url_glob: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """The ``top`` N largest resources by transferred size (bytes), largest first."""
        value = self._manager.get_largest_resources(top=int(top), url_glob=url_glob)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi largest resources", message
        )

    @keyword(name="Wait For BiDi Response", tags=("BiDi", "Network"))
    def wait_for_bidi_response(self, url_glob: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Block until a response whose URL matches ``url_glob`` is observed."""
        return self._manager.wait_for_response(url_glob, timeout=float(timeout))

    @keyword(name="Get BiDi Response Timing", tags=("BiDi", "Network", "Getter", "Assertion"))
    def get_bidi_response_timing(
        self,
        url_glob: str,
        phase: str = "ttfb",
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
    ) -> Optional[float]:
        """A single FetchTimingInfo phase in ms (dns/connect/tls/ttfb/download/total)
        for the last matching response — e.g. assert TTFB `<  ${500}`."""
        value = self._manager.get_response_timing(url_glob, phase)
        return verify_assertion(
            value, assertion_operator, assertion_expected, f"BiDi {phase} timing", message
        )

    # -- network interception keywords ------------------------------------

    @keyword(name="BiDi Mock Response", tags=("BiDi", "Network", "Intercept"))
    def bidi_mock_response(
        self, url_glob: str, status: int = 200,
        body: Optional[str] = None, headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Intercept requests matching ``url_glob`` and serve a mock response
        (status/body/headers) instead of hitting the server."""
        self._manager.add_mock(url_glob, status=int(status), headers=headers, body=body)

    @keyword(name="BiDi Fail Request", tags=("BiDi", "Network", "Intercept"))
    def bidi_fail_request(self, url_glob: str) -> None:
        """Fail (fault-inject) requests matching ``url_glob`` to exercise error handling."""
        self._manager.add_fault(url_glob)

    @keyword(name="BiDi Inject Headers", tags=("BiDi", "Network", "Intercept"))
    def bidi_inject_headers(self, url_glob: str, headers: Dict[str, str]) -> None:
        """Add request headers to requests matching ``url_glob`` (e.g. auth/test headers)."""
        self._manager.add_header_injection(url_glob, headers)

    @keyword(name="BiDi Provide Auth", tags=("BiDi", "Network", "Intercept"))
    def bidi_provide_auth(self, url_glob: str, username: str, password: str) -> None:
        """Answer HTTP auth challenges for matching requests via continueWithAuth."""
        self._manager.add_auth(url_glob, username, password)

    @keyword(name="BiDi Set Cache Behavior", tags=("BiDi", "Network", "Intercept"))
    def bidi_set_cache_behavior(self, cache_behavior: str = "bypass") -> None:
        """Set network cache behaviour (`default` or `bypass`)."""
        self._manager.set_cache_behavior(cache_behavior)

    @keyword(name="Clear BiDi Intercepts", tags=("BiDi", "Network", "Intercept"))
    def clear_bidi_intercepts(self) -> None:
        """Remove all registered intercepts/mocks/faults."""
        self._manager.clear_intercepts()

    # -- log keywords -----------------------------------------------------

    @keyword(name="Get BiDi Console Log", tags=("BiDi", "Log", "Getter", "Assertion"))
    def get_bidi_console_log(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        level: Optional[str] = None,
        since: Optional[int] = None,
        text: Optional[str] = None,
        pattern: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Console log entries, filtered by ``level``, ``text`` (case-insensitive
        substring), ``pattern`` (regex), and/or ``since``. E.g.
        ``Get BiDi Console Log  text=checkout  level=error``."""
        value = self._manager.get_console_log(level=level, since=since, text=text, pattern=pattern)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi console log", message
        )

    @keyword(name="Get BiDi Console Log Count", tags=("BiDi", "Log", "Getter", "Assertion"))
    def get_bidi_console_log_count(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        level: Optional[str] = None,
    ) -> int:
        """Number of buffered console log entries, optionally filtered by level."""
        value = self._manager.get_console_log_count(level=level)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi console log count", message
        )

    @keyword(name="Get BiDi JS Errors", tags=("BiDi", "Log", "Getter", "Assertion"))
    def get_bidi_js_errors(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        since: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return structured uncaught JS exceptions (empty list when none)."""
        value = self._manager.get_js_errors(since=since)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi JS errors", message
        )

    @keyword(name="Get BiDi JS Error Count", tags=("BiDi", "Log", "Getter", "Assertion"))
    def get_bidi_js_error_count(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
    ) -> int:
        """Number of uncaught JS exceptions captured (e.g. assert ``==  0``)."""
        value = self._manager.get_js_error_count()
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi JS error count", message
        )

    @keyword(name="Wait For BiDi Log Entry", tags=("BiDi", "Log"))
    def wait_for_bidi_log_entry(
        self, text: Optional[str] = None, level: Optional[str] = None, timeout: float = 10.0
    ) -> Dict[str, Any]:
        """Block until a log entry matches ``text`` (substring) and/or ``level``."""

        def matcher(entry: Dict[str, Any]) -> bool:
            if level is not None and entry.get("level") != level:
                return False
            if text is not None and text not in (entry.get("text") or ""):
                return False
            return True

        return self._manager.wait_for_log_entry(matcher, timeout=float(timeout))

    # -- script keywords --------------------------------------------------

    @keyword(name="BiDi Evaluate", tags=("BiDi", "Script", "Getter", "Assertion"))
    def bidi_evaluate(
        self,
        expression: str,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        realm: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Any:
        """Evaluate ``expression`` in a BiDi realm/context (defaults to current page).

        Optionally asserts on the returned value."""
        if realm is None and context is None:
            context = self.get_bidi_context_for_current_page()
        value = self._manager.evaluate(expression, realm=realm, context=context)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi evaluate", message
        )

    # -- page state / DOM getters -----------------------------------------

    def _page_context(self, context: Optional[str]) -> str:
        """Resolve a page-scoped context: explicit id, else the correlated
        current Playwright page (NOT the driver's initial blank tab)."""
        return context or self.get_bidi_context_for_current_page()

    @keyword(name="Get BiDi Url", tags=("BiDi", "PageContent", "Getter", "Assertion"))
    def get_bidi_url(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        context: Optional[str] = None,
    ) -> str:
        """Current page URL, read over BiDi (``window.location.href``)."""
        context = self._page_context(context)
        value = self._manager.get_url(context=context)
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi URL", message)

    @keyword(name="Get BiDi Title", tags=("BiDi", "PageContent", "Getter", "Assertion"))
    def get_bidi_title(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        context: Optional[str] = None,
    ) -> str:
        """Current page title, read over BiDi (``document.title``)."""
        context = self._page_context(context)
        value = self._manager.get_title(context=context)
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi title", message)

    @keyword(name="Get BiDi DOM Snapshot", tags=("BiDi", "PageContent", "Getter", "Assertion"))
    def get_bidi_dom_snapshot(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        context: Optional[str] = None,
    ) -> str:
        """Serialized DOM (``documentElement.outerHTML``) of the current context."""
        context = self._page_context(context)
        value = self._manager.get_dom_snapshot(context=context)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi DOM snapshot", message
        )

    @keyword(name="Get BiDi Aria Snapshot", tags=("BiDi", "Accessibility", "Getter", "Assertion"))
    def get_bidi_aria_snapshot(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        selector: Optional[str] = None,
        context: Optional[str] = None,
    ) -> str:
        """A Playwright-style ARIA snapshot (role + accessible name tree) of the page
        or a ``selector`` subtree — assert with ``contains`` on roles/names, e.g.
        ``Get BiDi Aria Snapshot  contains  - button "Sign in"``."""
        context = self._page_context(context)
        value = self._manager.get_aria_snapshot(selector=selector, context=context)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi aria snapshot", message
        )

    @keyword(name="Get BiDi Cookies", tags=("BiDi", "Storage", "Getter", "Assertion"))
    def get_bidi_cookies(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Cookies via BiDi ``storage.getCookies`` (optionally filtered by name)."""
        value = self._manager.get_cookies(name=name)
        return verify_assertion(value, assertion_operator, assertion_expected, "BiDi cookies", message)

    @keyword(name="Get BiDi Elements", tags=("BiDi", "DOM", "Getter", "Assertion"))
    def get_bidi_elements(
        self,
        strategy: str,
        value: str,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        context: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Locate nodes via BiDi ``browsingContext.locateNodes``.

        ``strategy`` is one of ``css``, ``xpath``, ``text`` (innerText), or
        ``accessibility`` (``value`` like ``role=button;name=Save``).

        Note: locators do NOT cross **shadow DOM** boundaries (standard selector
        semantics) — use `Get BiDi Element Count`/`Text` with ``pierce_shadow=True``
        to read open shadow roots. **Iframes** are separate browsing contexts:
        pass their ``context`` id (from `Get BiDi Context For Current Page` or the
        context tree)."""
        context = self._page_context(context)
        nodes = self._manager.locate_nodes(strategy, value, context=context)
        return verify_assertion(
            nodes, assertion_operator, assertion_expected, "BiDi elements", message
        )

    @keyword(name="Get BiDi Element Count", tags=("BiDi", "DOM", "Getter", "Assertion"))
    def get_bidi_element_count(
        self,
        strategy: str,
        value: str,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        context: Optional[str] = None,
        pierce_shadow: bool = False,
    ) -> int:
        """Count nodes matching a locator.

        With ``pierce_shadow=True`` (``css`` only) the count recurses into open
        shadow roots; otherwise shadow content is not crossed."""
        context = self._page_context(context)
        count = self._manager.get_element_count(
            strategy, value, context=context, pierce_shadow=pierce_shadow
        )
        return verify_assertion(
            count, assertion_operator, assertion_expected, "BiDi element count", message
        )

    @keyword(name="Get BiDi Element Text", tags=("BiDi", "DOM", "Getter", "Assertion"))
    def get_bidi_element_text(
        self,
        strategy: str,
        value: str,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        context: Optional[str] = None,
        pierce_shadow: bool = False,
    ) -> str:
        """``innerText`` of the first node matching a locator.

        With ``pierce_shadow=True`` (``css`` only) the search recurses into open
        shadow roots."""
        context = self._page_context(context)
        text = self._manager.get_element_text(
            strategy, value, context=context, pierce_shadow=pierce_shadow
        )
        return verify_assertion(
            text, assertion_operator, assertion_expected, "BiDi element text", message
        )

    @keyword(name="Get BiDi Web Vitals", tags=("BiDi", "Performance", "Getter", "Assertion"))
    def get_bidi_web_vitals(
        self,
        assertion_operator: Optional[AssertionOperator] = None,
        assertion_expected: Any = None,
        message: Optional[str] = None,
        *,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """UX timing via the Performance API: ttfb, domContentLoaded, load, fcp, lcp (ms)."""
        context = self._page_context(context)
        value = self._manager.get_web_vitals(context=context)
        return verify_assertion(
            value, assertion_operator, assertion_expected, "BiDi web vitals", message
        )

    @keyword(name="Take BiDi Screenshot", tags=("BiDi", "PageContent"))
    def take_bidi_screenshot(
        self, filename: Optional[str] = None, full_page: bool = False, context: Optional[str] = None
    ) -> str:
        """Capture a screenshot via BiDi ``browsingContext.captureScreenshot``.

        Returns base64 PNG data; if ``filename`` is given, also writes the decoded
        PNG to that path and returns the path."""
        data = self._manager.capture_screenshot(context=context, full_page=full_page)
        if filename:
            import base64
            from pathlib import Path

            Path(filename).write_bytes(base64.b64decode(data))
            return filename
        return data

    @keyword(name="BiDi Add Preload Script", tags=("BiDi", "Script"))
    def bidi_add_preload_script(
        self, function_body: str, sandbox: Optional[str] = None
    ) -> str:
        """Register a preload script that runs before page scripts."""
        return self._manager.add_preload_script(function_body, sandbox=sandbox)

    # -- emulation keywords (§7.4) ----------------------------------------

    @keyword(name="BiDi Set Geolocation", tags=("BiDi", "Emulation"))
    def bidi_set_geolocation(self, latitude: float, longitude: float, accuracy: float = 1.0,
                             context: Optional[str] = None) -> None:
        """Override geolocation for the current (or given) context."""
        self._manager.set_geolocation(float(latitude), float(longitude), float(accuracy),
                                      context=self._page_context(context))

    @keyword(name="BiDi Set Locale", tags=("BiDi", "Emulation"))
    def bidi_set_locale(self, locale: Optional[str] = None, context: Optional[str] = None) -> None:
        """Override locale (e.g. ``de-DE``); pass empty to clear."""
        self._manager.set_locale(locale or None, context=self._page_context(context))

    @keyword(name="BiDi Set Timezone", tags=("BiDi", "Emulation"))
    def bidi_set_timezone(self, timezone: Optional[str] = None, context: Optional[str] = None) -> None:
        """Override timezone (e.g. ``Europe/Berlin``); pass empty to clear."""
        self._manager.set_timezone(timezone or None, context=self._page_context(context))

    @keyword(name="BiDi Set User Agent", tags=("BiDi", "Emulation"))
    def bidi_set_user_agent(self, user_agent: Optional[str] = None, context: Optional[str] = None) -> None:
        """Override the user-agent string; pass empty to clear."""
        self._manager.set_user_agent(user_agent or None, context=self._page_context(context))

    @keyword(name="BiDi Set Forced Colors", tags=("BiDi", "Emulation"))
    def bidi_set_forced_colors(self, theme: Optional[str] = None, context: Optional[str] = None) -> None:
        """Emulate forced-colors mode (``light``/``dark``); pass empty to clear."""
        self._manager.set_forced_colors(theme or None, context=self._page_context(context))

    @keyword(name="BiDi Set Scripting Enabled", tags=("BiDi", "Emulation"))
    def bidi_set_scripting_enabled(self, enabled: bool = True, context: Optional[str] = None) -> None:
        """Enable/disable JavaScript to test no-JS graceful degradation."""
        self._manager.set_scripting_enabled(bool(enabled), context=self._page_context(context))

    @keyword(name="BiDi Set Viewport", tags=("BiDi", "Emulation"))
    def bidi_set_viewport(self, width: int, height: int, device_pixel_ratio: Optional[float] = None,
                          context: Optional[str] = None) -> None:
        """Set an exact viewport size for reproducible visual tests."""
        dpr = float(device_pixel_ratio) if device_pixel_ratio is not None else None
        self._manager.set_viewport(int(width), int(height), device_pixel_ratio=dpr,
                                   context=self._page_context(context))

    # -- user contexts (§7.2) ---------------------------------------------

    @keyword(name="New BiDi User Context", tags=("BiDi", "Isolation", "Setup"))
    def new_bidi_user_context(self) -> str:
        """Create an isolated user context (separate cookies/storage/cache).
        Returns its id; auto-removed on Disconnect BiDi."""
        return self._manager.create_user_context()

    @keyword(name="Remove BiDi User Context", tags=("BiDi", "Isolation", "Teardown"))
    def remove_bidi_user_context(self, user_context: str) -> None:
        """Remove a user context created via `New BiDi User Context`."""
        self._manager.remove_user_context(user_context)

    @keyword(name="New BiDi Context In User Context", tags=("BiDi", "Isolation"))
    def new_bidi_context_in_user_context(self, user_context: str, type: str = "tab") -> str:
        """Open a new browsing context (tab/window) inside a user context;
        returns its context id for use with the element/eval keywords."""
        return self._manager.create_context(user_context=user_context, type=type)

    # -- input & uploads (§7.9) -------------------------------------------

    @keyword(name="BiDi Set Files", tags=("BiDi", "Input"))
    def bidi_set_files(self, strategy: str, value: str, *files: str, context: Optional[str] = None) -> None:
        """Set files on a file input (incl. hidden inputs) located by ``strategy``/``value``."""
        self._manager.set_files(strategy, value, list(files), context=self._page_context(context))

    @keyword(name="BiDi Perform Actions", tags=("BiDi", "Input"))
    def bidi_perform_actions(self, actions: List[Dict[str, Any]], context: Optional[str] = None) -> None:
        """Run a raw BiDi Actions sequence (pointer/key/wheel source list)."""
        self._manager.perform_actions(actions, context=self._page_context(context))

    @keyword(name="BiDi Wheel Scroll", tags=("BiDi", "Input"))
    def bidi_wheel_scroll(self, delta_x: int = 0, delta_y: int = 0, x: int = 0, y: int = 0,
                          context: Optional[str] = None) -> None:
        """Scroll via a wheel action at ``x``/``y`` by ``delta_x``/``delta_y``."""
        self._manager.wheel_scroll(int(delta_x), int(delta_y), x=int(x), y=int(y),
                                   context=self._page_context(context))

    # -- storage writes (§7.7) --------------------------------------------

    @keyword(name="BiDi Set Cookie", tags=("BiDi", "Storage"))
    def bidi_set_cookie(self, name: str, value: str, domain: str, path: str = "/",
                        secure: bool = False, http_only: bool = False,
                        same_site: Optional[str] = None, expiry: Optional[int] = None) -> None:
        """Set a cookie via BiDi (e.g. seed an auth cookie to skip login)."""
        self._manager.set_cookie(name, value, domain, path=path, secure=bool(secure),
                                 http_only=bool(http_only), same_site=same_site,
                                 expiry=int(expiry) if expiry is not None else None)

    @keyword(name="BiDi Delete Cookies", tags=("BiDi", "Storage"))
    def bidi_delete_cookies(self, name: Optional[str] = None, domain: Optional[str] = None) -> None:
        """Delete cookies matching a name and/or domain filter."""
        self._manager.delete_cookies(name=name, domain=domain)

    # -- navigation & downloads (§7.3) ------------------------------------

    @keyword(name="Wait For BiDi Navigation", tags=("BiDi", "Navigation"))
    def wait_for_bidi_navigation(self, event: str = "load", timeout: float = 10.0,
                                 context: Optional[str] = None) -> Dict[str, Any]:
        """Wait for a navigation event (``load``/``domContentLoaded``/``navigationStarted``/
        ``fragmentNavigated``/``historyUpdated``/``navigationFailed``)."""
        return self._manager.wait_for_navigation(event, context=context, timeout=float(timeout))

    @keyword(name="Get BiDi Navigation Events", tags=("BiDi", "Navigation", "Getter"))
    def get_bidi_navigation_events(self, event: str = "load") -> List[Dict[str, Any]]:
        """Return buffered navigation events of the given type."""
        return self._manager.get_navigation_events(event)

    @keyword(name="BiDi Set Download Behavior", tags=("BiDi", "Download"))
    def bidi_set_download_behavior(self, destination_folder: Optional[str] = None,
                                   behavior: str = "allowed") -> None:
        """Configure download handling (and optional destination folder)."""
        self._manager.set_download_behavior(behavior=behavior, destination_folder=destination_folder)

    @keyword(name="Wait For BiDi Download", tags=("BiDi", "Download"))
    def wait_for_bidi_download(self, timeout: float = 30.0) -> Dict[str, Any]:
        """Wait for a download to complete; returns the downloadEnd event."""
        return self._manager.wait_for_download(timeout=float(timeout))

    # -- correlation (this plugin is the Browser HostAdapter) -------------

    def current_page_ref(self) -> PageRef:
        """HostAdapter contract: correlation hints for the active Playwright page,
        read from the bundled jsextension (CDP target id + URL)."""
        info = self.call_js_keyword("getCorrelationInfo") or {}
        return {"target_id": info.get("targetId"), "url": info.get("url")}

    @keyword(name="Get BiDi Context For Current Page", tags=("BiDi", "Correlation"))
    def get_bidi_context_for_current_page(self) -> Optional[str]:
        """Resolve the BiDi browsing-context id for the active Playwright page."""
        ref = self.current_page_ref()
        target_id = ref.get("target_id")
        url = ref.get("url")
        context_id = self._manager.context_for_page(target_id=target_id, url=url)
        if context_id is None:
            raise RuntimeError(
                "Could not correlate the current page to a BiDi context. Pass an "
                "explicit context id, or check that Connect BiDi targets the same browser."
            )
        return context_id

    @keyword(name="Get BiDi Contexts", tags=("BiDi", "DOM", "Getter"))
    def get_bidi_contexts(self) -> List[Dict[str, Any]]:
        """Flattened list of browsing contexts (top-level pages and nested
        iframes), each ``{context, url, parent}``. Use to target an iframe's
        context id for the element getters."""
        return self._manager.get_contexts()

    # -- diagnostics ------------------------------------------------------

    @keyword(name="Log BiDi Diagnostics", tags=("BiDi",))
    def log_bidi_diagnostics(self) -> Dict[str, Any]:
        """Log recent BiDi JS errors and buffer-drop counts; return them.

        Designed to be wired into Browser's run-on-failure, e.g.::

            Library    Browser    run_on_failure=Log BiDi Diagnostics

        so a failing test captures the BiDi-side state automatically. Safe to
        call when not connected (returns empty diagnostics).
        """
        if not self._manager.connected:
            return {"connected": False, "js_errors": [], "dropped_events": 0}
        diagnostics = {
            "connected": True,
            "js_errors": self._manager.get_js_errors(),
            "dropped_events": self._manager.dropped_event_count(),
        }
        logger.info(
            f"BiDi diagnostics: {len(diagnostics['js_errors'])} JS error(s), "
            f"{diagnostics['dropped_events']} dropped event(s)."
        )
        return diagnostics

    # -- internal ---------------------------------------------------------

    def _safe_teardown(self) -> None:
        try:
            self._manager.disconnect()
        except Exception:  # noqa: BLE001 - atexit must never raise
            pass
        self._close_launched()
