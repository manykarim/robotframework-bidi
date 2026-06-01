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
"""BiDi session orchestration, independent of the Browser library.

Ties together the loop runner, the swappable client, typed command wrappers,
and bounded buffers. The :class:`BrowserBiDi` plugin is a thin synchronous
facade over this manager; keeping the logic here lets it be unit-tested with a
fake client and no live browser.
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from .bidi_client import BiDiClient, BiDiError, WebsocketsBiDiClient
from .buffers import EventBuffers
from .commands import ALL_KNOWN_EVENTS, LOG_EVENTS, NETWORK_EVENTS, Commands
from .correlation import CorrelationCache, flatten_contexts, match_context
from .loop_runner import LoopRunner
from . import support
from .serialization import (
    compute_timing,
    headers_to_dict,
    normalize_cookie,
    remote_value_to_python,
    to_bidi_body,
    to_bidi_headers,
)

logger = logging.getLogger("bidi_core")

UNSUPPORTED_BROWSERS = {"webkit", "safari"}

# A factory so tests can inject a fake client; production uses websockets.
ClientFactory = Callable[[str], BiDiClient]


def _default_client_factory(url: str) -> BiDiClient:
    return WebsocketsBiDiClient(url)


def request_id_of(event: Dict[str, Any]) -> Optional[str]:
    request = event.get("request") or {}
    return request.get("request")


def request_url_of(event: Dict[str, Any]) -> Optional[str]:
    request = event.get("request") or {}
    return request.get("url")


class BiDiManager:
    def __init__(
        self,
        *,
        buffer_size: int = 1000,
        client_factory: ClientFactory = _default_client_factory,
        loop_runner: Optional[LoopRunner] = None,
    ) -> None:
        self._client_factory = client_factory
        self._buffers = EventBuffers(maxlen=buffer_size)
        self._loop = loop_runner or LoopRunner()
        self._client: Optional[BiDiClient] = None
        self._commands: Optional[Commands] = None
        self._correlation = CorrelationCache()
        self._subscribed: set[str] = set()
        self._collector: Optional[str] = None
        # Interception: phase -> intercept id; ordered list of declarative actions.
        self._intercepts: Dict[str, str] = {}
        self._actions: List[Dict[str, Any]] = []
        self._intercept_listener_installed = False
        self._user_contexts: set[str] = set()
        self._browser: Optional[str] = None
        self._answer_tasks: set = set()  # in-flight intercept-answer tasks (GC guard)

    # -- lifecycle ---------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._client is not None

    def connect(
        self,
        url: str,
        *,
        browser: Optional[str] = None,
        auto_subscribe: Optional[List[str]] = None,
        timeout: float = 30.0,
        transport: str = "websocket",
    ) -> None:
        if browser and browser.lower() in UNSUPPORTED_BROWSERS:
            raise BiDiError(
                "unsupported browser",
                f"WebDriver BiDi is not available for '{browser}'. "
                "Supported: chromium/chrome, edge, firefox.",
            )
        self._browser = browser
        self._loop.start()
        if transport == "cdp-mapper":
            # Driverless Chrome: ``url`` is the CDP webSocketDebuggerUrl; speak
            # BiDi through the chromium-bidi mapper loaded into a hidden tab.
            from .mapper_client import MapperBiDiClient

            client: BiDiClient = MapperBiDiClient(url)
        elif transport == "websocket":
            client = self._client_factory(url)
        else:
            self._loop.stop()
            raise BiDiError("bad transport", f"Unknown transport '{transport}'.")
        try:
            self._loop.run(client.connect(), timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - turn any connect failure actionable
            self._loop.stop()
            raise BiDiError(
                "connect failed",
                f"Could not open a BiDi WebSocket at '{url}'. Ensure the browser was "
                f"launched with BiDi reachable (see README launch contract). Cause: {exc}",
            ) from exc
        self._client = client
        self._commands = Commands(client)
        self._register_buffering_listeners()
        # A driver-provided webSocketUrl is already an established session, so
        # session.new is redundant there and may error; treat it as best-effort
        # rather than failing the whole connect.
        try:
            self._loop.run(self._commands.session.new(), timeout=min(timeout, 5))
        except Exception:  # noqa: BLE001 - session may already exist on this socket
            pass
        # Register a response-body data collector up front: Chrome only retains
        # bodies for getData if a collector exists before the response (found
        # via the Phase 0 spike). Best-effort: not all browsers support it.
        try:
            result = self._loop.run(self._commands.network.add_data_collector(), timeout=min(timeout, 5))
            self._collector = result.get("collector")
        except Exception:  # noqa: BLE001
            self._collector = None
        if auto_subscribe:
            self.subscribe(auto_subscribe)

    def disconnect(self) -> None:
        """Unsubscribe, close the socket, stop the loop. Best-effort."""
        if self._client is None:
            self._loop.stop()
            return
        try:
            if self._subscribed and self._commands is not None:
                self._loop.run(
                    self._commands.session.unsubscribe(sorted(self._subscribed)), timeout=10
                )
        except Exception:  # noqa: BLE001 - teardown must not raise
            pass
        for user_context in list(self._user_contexts):  # remove created isolation
            try:
                if self._commands is not None:
                    self._loop.run(self._commands.browser.remove_user_context(user_context), timeout=5)
            except Exception:  # noqa: BLE001
                pass
        try:
            self._loop.run(self._client.close(), timeout=10)
        except Exception:  # noqa: BLE001
            pass
        self._loop.stop()
        self._client = None
        self._commands = None
        self._subscribed.clear()
        self._buffers.clear()
        self._correlation.clear()
        self._collector = None
        self._intercepts.clear()
        self._actions.clear()
        self._intercept_listener_installed = False
        self._user_contexts.clear()

    def _require(self) -> Commands:
        if self._commands is None:
            raise BiDiError("not connected", "Call 'Connect BiDi' before using BiDi keywords.")
        return self._commands

    # -- subscriptions & buffering ----------------------------------------

    def _register_buffering_listeners(self) -> None:
        assert self._client is not None
        for method in ALL_KNOWN_EVENTS:
            self._client.add_event_listener(
                method, lambda params, m=method: self._buffers.append(m, params)
            )

    def subscribe(self, events: List[str], timeout: float = 10.0) -> None:
        commands = self._require()
        self._loop.run(commands.session.subscribe(events), timeout=timeout)
        self._subscribed.update(events)

    def unsubscribe(self, events: List[str], timeout: float = 10.0) -> None:
        commands = self._require()
        self._loop.run(commands.session.unsubscribe(events), timeout=timeout)
        self._subscribed.difference_update(events)

    # -- network ----------------------------------------------------------

    def get_network_events(
        self, *, url_glob: Optional[str] = None, since: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        def matches(event: Dict[str, Any]) -> bool:
            if url_glob is None:
                return True
            url = request_url_of(event) or ""
            return fnmatch.fnmatch(url, url_glob)

        events: List[Dict[str, Any]] = []
        for method in NETWORK_EVENTS:
            events.extend(self._buffers.buffer(method).get(since=since, predicate=matches))
        return events

    def get_response_body(self, request_id: str, timeout: float = 10.0) -> str:
        commands = self._require()
        try:
            result = self._loop.run(
                commands.network.get_data(request_id, collector=self._collector), timeout=timeout
            )
        except BiDiError as exc:
            raise BiDiError(
                "response body unavailable",
                f"No retrievable response body for request '{request_id}'. "
                f"Cause: {exc}",
            ) from exc
        # network.getData returns a serialized value; surface its text payload.
        bytes_value = result.get("bytes") or {}
        return bytes_value.get("value", "")

    def wait_for_response(
        self, url_glob: str, timeout: float = 10.0
    ) -> Dict[str, Any]:
        def predicate(params: Dict[str, Any]) -> bool:
            return fnmatch.fnmatch(request_url_of(params) or "", url_glob)

        # Check already-buffered completed responses first, then wait.
        buffered = self._buffers.buffer("network.responseCompleted").get(predicate=predicate)
        if buffered:
            return buffered[-1]
        return self._loop.run(
            self._wait_event(("network.responseCompleted",), predicate, timeout),
            timeout=timeout + 1,
        )

    # -- log --------------------------------------------------------------

    def get_console_log(
        self, *, level: Optional[str] = None, since: Optional[int] = None,
        text: Optional[str] = None, pattern: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Console log entries, filtered by ``level``, ``text`` (case-insensitive
        substring) and/or ``pattern`` (regular expression on the message text)."""
        regex = re.compile(pattern) if pattern else None
        needle = text.lower() if text else None

        def matches(event: Dict[str, Any]) -> bool:
            if level is not None and event.get("level") != level:
                return False
            message = event.get("text") or ""
            if needle is not None and needle not in message.lower():
                return False
            if regex is not None and not regex.search(message):
                return False
            return True

        return self._buffers.buffer("log.entryAdded").get(since=since, predicate=matches)

    # -- accessibility snapshot (heuristic, via script.evaluate) ----------

    def get_aria_snapshot(self, *, selector: Optional[str] = None,
                          context: Optional[str] = None) -> str:
        """A Playwright-style ARIA snapshot of the page (or a ``selector`` subtree),
        computed in-page over the DOM. Heuristic accessible-role/name computation
        (covers common roles), so it works cross-engine via BiDi without a native
        a11y-tree API."""
        ctx = self._resolve_context(context)
        expr = self._ARIA_SNAPSHOT_JS % json.dumps(selector)
        return self.evaluate(expr, context=ctx) or ""

    _ARIA_SNAPSHOT_JS = r"""(() => {
      const sel = %s;
      const root = sel ? document.querySelector(sel) : document.body;
      if (!root) return '';
      const IMPLICIT = {a:'link', button:'button', h1:'heading', h2:'heading', h3:'heading',
        h4:'heading', h5:'heading', h6:'heading', img:'img', ul:'list', ol:'list', li:'listitem',
        nav:'navigation', main:'main', form:'form', table:'table', select:'combobox',
        textarea:'textbox'};
      const role = (el) => {
        if (el.getAttribute('role')) return el.getAttribute('role');
        const t = el.tagName.toLowerCase();
        if (t === 'a') return el.hasAttribute('href') ? 'link' : null;
        if (t === 'input') {
          const m = {text:'textbox', search:'searchbox', checkbox:'checkbox', radio:'radio',
            button:'button', submit:'button', email:'textbox', password:'textbox', number:'spinbutton'};
          return m[el.type] || 'textbox';
        }
        return IMPLICIT[t] || null;
      };
      const name = (el) => {
        if (el.getAttribute('aria-label')) return el.getAttribute('aria-label').trim();
        const lb = el.getAttribute('aria-labelledby');
        if (lb) { const e = document.getElementById(lb); if (e) return (e.textContent||'').trim(); }
        if (el.tagName === 'IMG') return (el.getAttribute('alt')||'').trim();
        if (el.getAttribute('placeholder')) return el.getAttribute('placeholder').trim();
        if (el.title) return el.title.trim();
        const own = Array.from(el.childNodes).filter(n => n.nodeType === 3)
          .map(n => n.textContent).join(' ').trim();
        const txt = (own || el.textContent || '').replace(/\s+/g, ' ').trim();
        return txt.slice(0, 100);
      };
      const walk = (el, depth) => {
        let out = '';
        for (const child of el.children) {
          if (child.hidden || child.getAttribute('aria-hidden') === 'true') continue;
          const r = role(child);
          if (r) {
            const n = name(child);
            const lvl = r === 'heading' ? ` [level=${child.tagName[1] || ''}]` : '';
            out += '  '.repeat(depth) + `- ${r}` + (n ? ` "${n}"` : '') + lvl + '\n';
            out += walk(child, depth + 1);
          } else {
            out += walk(child, depth);
          }
        }
        return out;
      };
      return walk(root, 0).trimEnd();
    })()"""

    def get_js_errors(self, *, since: Optional[int] = None) -> List[Dict[str, Any]]:
        def is_js_error(event: Dict[str, Any]) -> bool:
            return event.get("type") == "javascript" and event.get("level") == "error"

        return self._buffers.buffer("log.entryAdded").get(since=since, predicate=is_js_error)

    def wait_for_log_entry(
        self, matcher: Callable[[Dict[str, Any]], bool], timeout: float = 10.0
    ) -> Dict[str, Any]:
        buffered = self._buffers.buffer("log.entryAdded").get(predicate=matcher)
        if buffered:
            return buffered[-1]
        return self._loop.run(
            self._wait_event(LOG_EVENTS, matcher, timeout), timeout=timeout + 1
        )

    async def _wait_event(
        self,
        methods: tuple,
        predicate: Callable[[Dict[str, Any]], bool],
        timeout: float,
    ) -> Dict[str, Any]:
        assert self._client is not None
        loop = asyncio.get_event_loop()
        future: "asyncio.Future[Dict[str, Any]]" = loop.create_future()

        def listener(params: Dict[str, Any]) -> None:
            if not future.done() and predicate(params):
                future.set_result(params)

        for method in methods:
            self._client.add_event_listener(method, listener)
        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError as exc:
            raise BiDiError("timeout", f"No matching event within {timeout}s") from exc
        finally:
            for method in methods:
                self._client.remove_event_listener(method, listener)

    # -- script -----------------------------------------------------------

    def evaluate(
        self, expression: str, *, realm: Optional[str] = None, context: Optional[str] = None
    ) -> Any:
        commands = self._require()
        if realm:
            target: Dict[str, Any] = {"realm": realm}
        elif context:
            target = {"context": context}
        else:
            raise BiDiError(
                "no target", "Provide a realm or context (or a correlated current page)."
            )
        result = self._loop.run(commands.script.evaluate(expression, target), timeout=30)
        if result.get("type") == "exception":
            details = result.get("exceptionDetails", {})
            raise BiDiError("script exception", details.get("text", "evaluation threw"))
        return result.get("result", {}).get("value")

    def add_preload_script(self, function_declaration: str, *, sandbox: Optional[str] = None) -> str:
        commands = self._require()
        result = self._loop.run(
            commands.script.add_preload_script(function_declaration, sandbox=sandbox), timeout=10
        )
        return result.get("script", "")

    # -- correlation ------------------------------------------------------

    def context_for_page(
        self, *, target_id: Optional[str] = None, url: Optional[str] = None
    ) -> Optional[str]:
        # Only the target-id mapping is cached: a CDP target id is stable across
        # navigations, so caching it is safe. URL-only matches (e.g. Firefox,
        # which has no target id) are recomputed every call, which makes them
        # inherently fresh after a navigation (design.md D6, "refresh on
        # navigation").
        if target_id:
            cached = self._correlation.get(target_id)
            if cached:
                return cached
        commands = self._require()
        tree = self._loop.run(commands.browsing_context.get_tree(), timeout=10)
        context_id = match_context(tree.get("contexts", []), target_id=target_id, url=url)
        if context_id and target_id:
            self._correlation.put(target_id, context_id)
        return context_id

    def invalidate_correlation(self, target_id: str) -> None:
        self._correlation.invalidate(target_id)

    def get_contexts(self) -> List[Dict[str, Any]]:
        """Flattened browsing-context tree (top-level pages and nested iframes)."""
        commands = self._require()
        tree = self._loop.run(commands.browsing_context.get_tree(), timeout=10)
        return [
            {"context": c.get("context"), "url": c.get("url"), "parent": c.get("parent")}
            for c in flatten_contexts(tree.get("contexts", []))
        ]

    def _resolve_context(self, context: Optional[str]) -> str:
        """Return an explicit context id, else the first top-level context."""
        if context:
            return context
        commands = self._require()
        tree = self._loop.run(commands.browsing_context.get_tree(), timeout=10)
        contexts = tree.get("contexts", [])
        if not contexts:
            raise BiDiError("no context", "No browsing context available.")
        return contexts[0]["context"]

    # -- page state (script-backed) ---------------------------------------

    def get_url(self, *, context: Optional[str] = None) -> str:
        return self.evaluate("window.location.href", context=self._resolve_context(context)) or ""

    def get_title(self, *, context: Optional[str] = None) -> str:
        return self.evaluate("document.title", context=self._resolve_context(context)) or ""

    def get_dom_snapshot(self, *, context: Optional[str] = None) -> str:
        return self.evaluate(
            "document.documentElement.outerHTML", context=self._resolve_context(context)
        ) or ""

    # -- network getters --------------------------------------------------

    def _matching_responses(self, url_glob: Optional[str]) -> List[Dict[str, Any]]:
        def matches(event: Dict[str, Any]) -> bool:
            if url_glob is None:
                return True
            return fnmatch.fnmatch(request_url_of(event) or "", url_glob)

        return self._buffers.buffer("network.responseCompleted").get(predicate=matches)

    def get_response_status(self, url_glob: str) -> int:
        events = self._matching_responses(url_glob)
        if not events:
            raise BiDiError("no response", f"No captured response matching '{url_glob}'.")
        return int((events[-1].get("response") or {}).get("status"))

    def get_response_headers(self, url_glob: str) -> Dict[str, str]:
        events = self._matching_responses(url_glob)
        if not events:
            raise BiDiError("no response", f"No captured response matching '{url_glob}'.")
        return headers_to_dict((events[-1].get("response") or {}).get("headers"))

    def get_network_event_count(
        self, *, url_glob: Optional[str] = None, event_type: Optional[str] = None
    ) -> int:
        types = (event_type,) if event_type else NETWORK_EVENTS
        return len(self.get_network_events(url_glob=url_glob)) if event_type is None else sum(
            len(self._buffers.buffer(t).get(
                predicate=lambda e: url_glob is None or fnmatch.fnmatch(request_url_of(e) or "", url_glob)
            )) for t in types
        )

    # Fields a resource entry can be sorted/asserted on.
    RESOURCE_FIELDS = ("dns", "connect", "tls", "ttfb", "download", "total", "size")

    def get_resource_timings(
        self, *, url_glob: Optional[str] = None, sort_by: Optional[str] = None,
        top: Optional[int] = None, descending: bool = True,
    ) -> List[Dict[str, Any]]:
        """Per-resource timing + size, optionally sorted by a field and limited
        to the top N. Each entry: dns/connect/tls/ttfb/download/total (ms),
        size (bytes), url, status, mime, from_cache."""
        out: List[Dict[str, Any]] = []
        for event in self._matching_responses(url_glob):
            request = event.get("request") or {}
            response = event.get("response") or {}
            entry = compute_timing(request.get("timings"))
            entry["url"] = request.get("url")
            entry["size"] = response.get("bytesReceived") or response.get("bodySize") or 0
            entry["status"] = response.get("status")
            entry["mime"] = response.get("mimeType")
            entry["from_cache"] = response.get("fromCache")
            out.append(entry)
        if sort_by:
            if sort_by not in self.RESOURCE_FIELDS:
                raise BiDiError("bad sort", f"Unknown sort field '{sort_by}'. Use {self.RESOURCE_FIELDS}.")
            out.sort(key=lambda e: (e.get(sort_by) is not None, e.get(sort_by) or 0), reverse=descending)
        if top is not None:
            out = out[: int(top)]
        return out

    def get_slowest_resources(self, *, top: int = 10, phase: str = "total",
                              url_glob: Optional[str] = None) -> List[Dict[str, Any]]:
        """Top N resources by a timing phase (default total load time), slowest first."""
        return self.get_resource_timings(url_glob=url_glob, sort_by=phase, top=top, descending=True)

    def get_largest_resources(self, *, top: int = 10,
                              url_glob: Optional[str] = None) -> List[Dict[str, Any]]:
        """Top N resources by transferred size (bytes), largest first."""
        return self.get_resource_timings(url_glob=url_glob, sort_by="size", top=top, descending=True)

    def get_response_timing(self, url_glob: str, phase: str = "ttfb") -> Optional[float]:
        """A single FetchTimingInfo phase (dns/connect/tls/ttfb/download/total, ms)
        for the last response matching ``url_glob`` — for threshold assertions."""
        events = self._matching_responses(url_glob)
        if not events:
            raise BiDiError("no response", f"No captured response matching '{url_glob}'.")
        timing = compute_timing((events[-1].get("request") or {}).get("timings"))
        if phase not in timing:
            raise BiDiError("bad phase", f"Unknown timing phase '{phase}'. Use {sorted(timing)}.")
        return timing[phase]

    # -- network interception (§7.5.3, §7.5.5) ---------------------------

    def _ensure_intercept(self, phase: str, event: str) -> None:
        """Lazily subscribe to the phase event, install the answering listener,
        and register a catch-all intercept so matching requests pause."""
        commands = self._require()
        if not self._intercept_listener_installed:
            assert self._client is not None
            self._client.add_event_listener("network.beforeRequestSent", self._on_intercepted)
            self._client.add_event_listener("network.authRequired", self._on_auth_required)
            self._intercept_listener_installed = True
        if event not in self._subscribed:
            self.subscribe([event])
        if phase not in self._intercepts:
            result = self._loop.run(commands.network.add_intercept([phase]), timeout=10)
            self._intercepts[phase] = result.get("intercept", "")

    def add_mock(self, url_glob: str, *, status: int = 200,
                 headers: Optional[Dict[str, str]] = None, body: Optional[str] = None) -> None:
        self._ensure_intercept("beforeRequestSent", "network.beforeRequestSent")
        self._actions.append({"phase": "beforeRequestSent", "glob": url_glob, "kind": "mock",
                              "status": status, "headers": headers or {}, "body": body or ""})

    def add_fault(self, url_glob: str) -> None:
        self._ensure_intercept("beforeRequestSent", "network.beforeRequestSent")
        self._actions.append({"phase": "beforeRequestSent", "glob": url_glob, "kind": "fail"})

    def add_header_injection(self, url_glob: str, headers: Dict[str, str]) -> None:
        self._ensure_intercept("beforeRequestSent", "network.beforeRequestSent")
        self._actions.append({"phase": "beforeRequestSent", "glob": url_glob, "kind": "headers",
                              "headers": headers})

    def add_auth(self, url_glob: str, username: str, password: str) -> None:
        self._ensure_intercept("authRequired", "network.authRequired")
        self._actions.append({"phase": "authRequired", "glob": url_glob, "kind": "auth",
                              "username": username, "password": password})

    def clear_intercepts(self) -> None:
        commands = self._commands
        for intercept in list(self._intercepts.values()):
            try:
                if commands is not None and intercept:
                    self._loop.run(commands.network.remove_intercept(intercept), timeout=5)
            except Exception:  # noqa: BLE001
                pass
        self._intercepts.clear()
        self._actions.clear()

    def set_cache_behavior(self, cache_behavior: str) -> None:
        commands = self._require()
        self._loop.run(commands.network.set_cache_behavior(cache_behavior), timeout=10)

    def _match_action(self, phase: str, url: str) -> Optional[Dict[str, Any]]:
        for action in self._actions:
            if action["phase"] == phase and fnmatch.fnmatch(url or "", action["glob"]):
                return action
        return None

    def _on_intercepted(self, params: Dict[str, Any]) -> None:
        # Runs on the loop thread; schedule the answer without blocking dispatch.
        if not params.get("isBlocked"):
            return
        request_id = request_id_of(params)
        if not request_id:
            return
        action = self._match_action("beforeRequestSent", request_url_of(params) or "")
        self._schedule(self._answer_request(request_id, action))

    def _on_auth_required(self, params: Dict[str, Any]) -> None:
        if not params.get("isBlocked"):
            return
        request_id = request_id_of(params)
        if not request_id:
            return
        action = self._match_action("authRequired", request_url_of(params) or "")
        self._schedule(self._answer_auth(request_id, action))

    async def _answer_request(self, request_id: str, action: Optional[Dict[str, Any]]) -> None:
        commands = self._commands
        if commands is None:
            return
        try:
            net = commands.network
            if action is None:
                await net.continue_request(request_id)  # auto-continue fallback
            elif action["kind"] == "mock":
                await net.provide_response(
                    request_id, status_code=action["status"],
                    headers=to_bidi_headers(action["headers"]) or None,
                    body=to_bidi_body(action["body"]))
            elif action["kind"] == "fail":
                await net.fail_request(request_id)
            elif action["kind"] == "headers":
                await net.continue_request(request_id, headers=to_bidi_headers(action["headers"]))
            else:
                await net.continue_request(request_id)
        except Exception as exc:  # noqa: BLE001 - never let an answer crash the loop
            logger.warning("BiDi intercept answer failed for %s: %s", request_id, exc)

    async def _answer_auth(self, request_id: str, action: Optional[Dict[str, Any]]) -> None:
        commands = self._commands
        if commands is None:
            return
        try:
            if action is None:
                await commands.network.continue_with_auth(request_id, action="default")
            else:
                await commands.network.continue_with_auth(
                    request_id, action="provideCredentials",
                    username=action["username"], password=action["password"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("BiDi auth answer failed for %s: %s", request_id, exc)

    def _schedule(self, coro) -> None:
        """Schedule a coroutine on the background loop from a listener callback.

        In production the listener runs on the loop thread (the reader dispatches
        there), so we create a task on the running loop. Off the loop thread
        (e.g. tests) we submit threadsafe and wait."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            task = loop.create_task(coro)
            # Keep a reference so the task isn't GC'd mid-flight, and drop it when done.
            self._answer_tasks.add(task)
            task.add_done_callback(self._answer_tasks.discard)
        else:
            self._loop.run(coro, timeout=10)

    # -- log getters ------------------------------------------------------

    def get_console_log_count(self, *, level: Optional[str] = None) -> int:
        return len(self.get_console_log(level=level))

    def get_js_error_count(self) -> int:
        return len(self.get_js_errors())

    # -- cookies ----------------------------------------------------------

    def get_cookies(self, *, name: Optional[str] = None) -> List[Dict[str, Any]]:
        commands = self._require()
        filter_ = {"name": name} if name else None
        result = self._loop.run(commands.storage.get_cookies(filter=filter_), timeout=10)
        return [normalize_cookie(c) for c in result.get("cookies", [])]

    # -- DOM / elements (locateNodes: pierces open shadow DOM) ------------

    def locate_nodes(
        self,
        strategy: str,
        value: str,
        *,
        context: Optional[str] = None,
        max_count: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        commands = self._require()
        ctx = self._resolve_context(context)
        locator = self._build_locator(strategy, value)
        result = self._loop.run(
            commands.browsing_context.locate_nodes(ctx, locator, max_node_count=max_count),
            timeout=15,
        )
        return [remote_value_to_python(n) for n in result.get("nodes", [])]

    @staticmethod
    def _build_locator(strategy: str, value: str) -> Dict[str, Any]:
        s = strategy.lower()
        if s == "css":
            return {"type": "css", "value": value}
        if s == "xpath":
            return {"type": "xpath", "value": value}
        if s in ("text", "innertext"):
            return {"type": "innerText", "value": value}
        if s in ("accessibility", "a11y"):
            # value is "role" or "role=...;name=..."; support a simple form.
            parts = dict(p.split("=", 1) for p in value.split(";") if "=" in p)
            acc = {}
            if parts.get("role"):
                acc["role"] = parts["role"]
            if parts.get("name"):
                acc["name"] = parts["name"]
            if not acc:
                acc["role"] = value
            return {"type": "accessibility", "value": acc}
        raise BiDiError("bad locator", f"Unknown locator strategy '{strategy}'.")

    # Deep query that recurses into OPEN shadow roots — plain CSS locators do
    # NOT cross shadow boundaries, so this is the way to read shadow DOM.
    _DEEP_COUNT_JS = (
        "(() => { const sel = %s; const out = new Set();"
        " const walk = (root) => { root.querySelectorAll(sel).forEach(e => out.add(e));"
        " root.querySelectorAll('*').forEach(e => { if (e.shadowRoot) walk(e.shadowRoot); }); };"
        " walk(document); return out.size; })()"
    )
    _DEEP_TEXT_JS = (
        "(() => { const sel = %s; let found = null;"
        " const walk = (root) => { if (found) return; const m = root.querySelector(sel);"
        " if (m) { found = m; return; }"
        " root.querySelectorAll('*').forEach(e => { if (!found && e.shadowRoot) walk(e.shadowRoot); }); };"
        " walk(document); return found ? found.innerText : null; })()"
    )

    def get_element_count(
        self,
        strategy: str,
        value: str,
        *,
        context: Optional[str] = None,
        pierce_shadow: bool = False,
    ) -> int:
        if pierce_shadow:
            if strategy.lower() != "css":
                raise BiDiError("bad locator", "pierce_shadow is only supported with the 'css' strategy.")
            ctx = self._resolve_context(context)
            return int(self.evaluate(self._DEEP_COUNT_JS % json.dumps(value), context=ctx) or 0)
        return len(self.locate_nodes(strategy, value, context=context))

    def get_element_text(
        self,
        strategy: str,
        value: str,
        *,
        context: Optional[str] = None,
        pierce_shadow: bool = False,
    ) -> str:
        commands = self._require()
        ctx = self._resolve_context(context)
        if pierce_shadow:
            if strategy.lower() != "css":
                raise BiDiError("bad locator", "pierce_shadow is only supported with the 'css' strategy.")
            text = self.evaluate(self._DEEP_TEXT_JS % json.dumps(value), context=ctx)
            if text is None:
                raise BiDiError("no element", f"No element matched css={value!r} (incl. shadow DOM).")
            return text
        nodes_result = self._loop.run(
            commands.browsing_context.locate_nodes(ctx, self._build_locator(strategy, value), max_node_count=1),
            timeout=15,
        )
        nodes = nodes_result.get("nodes", [])
        if not nodes:
            raise BiDiError("no element", f"No element matched {strategy}={value!r}.")
        shared_id = nodes[0].get("sharedId")
        result = self._loop.run(
            commands.script.call_function(
                "(el) => el.innerText",
                {"context": ctx},
                arguments=[{"sharedId": shared_id}],
            ),
            timeout=10,
        )
        return (result.get("result", {}) or {}).get("value") or ""

    # -- screenshot -------------------------------------------------------

    def capture_screenshot(
        self, *, context: Optional[str] = None, full_page: bool = False
    ) -> str:
        commands = self._require()
        ctx = self._resolve_context(context)
        origin = "document" if full_page else "viewport"
        result = self._loop.run(
            commands.browsing_context.capture_screenshot(ctx, origin=origin), timeout=20
        )
        return result.get("data", "")

    # -- web vitals -------------------------------------------------------

    def get_web_vitals(self, *, context: Optional[str] = None) -> Dict[str, Any]:
        ctx = self._resolve_context(context)
        # Collect navigation + paint + buffered LCP via the Performance APIs.
        script = (
            "JSON.stringify((() => {"
            "  const nav = performance.getEntriesByType('navigation')[0] || {};"
            "  const paint = performance.getEntriesByType('paint');"
            "  const fcp = (paint.find(p => p.name === 'first-contentful-paint') || {}).startTime;"
            "  const lcpList = performance.getEntriesByType('largest-contentful-paint');"
            "  const lcp = lcpList.length ? lcpList[lcpList.length - 1].startTime : null;"
            "  return {"
            "    ttfb: nav.responseStart ?? null,"
            "    domContentLoaded: nav.domContentLoadedEventEnd ?? null,"
            "    load: nav.loadEventEnd ?? null,"
            "    fcp: fcp ?? null,"
            "    lcp: lcp"
            "  };"
            "})())"
        )
        raw = self.evaluate(script, context=ctx)
        return json.loads(raw) if raw else {}

    # -- capability gating (§ support matrix, design.md D5) ---------------

    def _run_gated(self, bidi_method: str, coro, timeout: float):
        """Run a control-side command with capability gating: fail fast if the
        matrix marks it unsupported on the active engine, and translate runtime
        'unsupported operation' errors into the same actionable message."""
        if support.is_supported(bidi_method, self._browser) is False:
            raise BiDiError("unsupported", support.unsupported_message(bidi_method, self._browser))
        try:
            return self._loop.run(coro, timeout=timeout)
        except BiDiError as exc:
            if support.is_unsupported_error(str(exc)):
                raise BiDiError("unsupported",
                                support.unsupported_message(bidi_method, self._browser)) from exc
            raise

    # -- emulation (§7.4) -------------------------------------------------

    def set_geolocation(self, latitude: float, longitude: float, accuracy: float = 1.0,
                        *, context: Optional[str] = None) -> None:
        commands = self._require()
        ctx = [context] if context else None
        self._run_gated("emulation.setGeolocationOverride", commands.emulation.set_geolocation(
            latitude=latitude, longitude=longitude, accuracy=accuracy, contexts=ctx), 10)

    def set_locale(self, locale: Optional[str], *, context: Optional[str] = None) -> None:
        commands = self._require()
        self._run_gated("emulation.setLocaleOverride",
                        commands.emulation.set_locale(locale, contexts=[context] if context else None), 10)

    def set_timezone(self, timezone: Optional[str], *, context: Optional[str] = None) -> None:
        commands = self._require()
        self._run_gated("emulation.setTimezoneOverride",
                        commands.emulation.set_timezone(timezone, contexts=[context] if context else None), 10)

    def set_user_agent(self, user_agent: Optional[str], *, context: Optional[str] = None) -> None:
        commands = self._require()
        self._run_gated("emulation.setUserAgentOverride",
                        commands.emulation.set_user_agent(user_agent, contexts=[context] if context else None), 10)

    def set_forced_colors(self, theme: Optional[str], *, context: Optional[str] = None) -> None:
        commands = self._require()
        self._run_gated("emulation.setForcedColorsModeThemeOverride",
                        commands.emulation.set_forced_colors(theme, contexts=[context] if context else None), 10)

    def set_scripting_enabled(self, enabled: Optional[bool], *, context: Optional[str] = None) -> None:
        commands = self._require()
        self._run_gated("emulation.setScriptingEnabled",
                        commands.emulation.set_scripting_enabled(enabled, contexts=[context] if context else None), 10)

    def set_viewport(self, width: int, height: int, *, device_pixel_ratio: Optional[float] = None,
                     context: Optional[str] = None) -> None:
        commands = self._require()
        ctx = self._resolve_context(context)
        self._loop.run(commands.browsing_context.set_viewport(
            ctx, width=width, height=height, device_pixel_ratio=device_pixel_ratio), timeout=10)

    # -- user contexts (§7.2) ---------------------------------------------

    def create_user_context(self) -> str:
        commands = self._require()
        user_context = self._loop.run(commands.browser.create_user_context(), timeout=10).get("userContext", "")
        if user_context:
            self._user_contexts.add(user_context)
        return user_context

    def remove_user_context(self, user_context: str) -> None:
        commands = self._require()
        self._loop.run(commands.browser.remove_user_context(user_context), timeout=10)
        self._user_contexts.discard(user_context)

    def create_context(self, *, user_context: Optional[str] = None, type: str = "tab") -> str:
        commands = self._require()
        result = self._loop.run(
            commands.browsing_context.create(type=type, user_context=user_context), timeout=15)
        return result.get("context", "")

    # -- input & uploads (§7.9) -------------------------------------------

    def perform_actions(self, actions: List[Dict[str, Any]], *, context: Optional[str] = None) -> None:
        commands = self._require()
        self._loop.run(commands.input.perform_actions(self._resolve_context(context), actions), timeout=20)

    def wheel_scroll(self, delta_x: int, delta_y: int, *, x: int = 0, y: int = 0,
                     context: Optional[str] = None) -> None:
        actions = [{"type": "wheel", "id": "wheel", "actions": [
            {"type": "scroll", "x": x, "y": y, "deltaX": delta_x, "deltaY": delta_y}]}]
        self.perform_actions(actions, context=context)

    def set_files(self, strategy: str, value: str, files: List[str], *, context: Optional[str] = None) -> None:
        commands = self._require()
        ctx = self._resolve_context(context)
        nodes = self._loop.run(
            commands.browsing_context.locate_nodes(ctx, self._build_locator(strategy, value), max_node_count=1),
            timeout=15)
        located = nodes.get("nodes", [])
        if not located:
            raise BiDiError("no element", f"No file input matched {strategy}={value!r}.")
        element = {"sharedId": located[0].get("sharedId")}
        self._loop.run(commands.input.set_files(ctx, element, list(files)), timeout=15)

    # -- storage writes (§7.7) --------------------------------------------

    def set_cookie(self, name: str, value: str, domain: str, *, path: str = "/",
                   secure: bool = False, http_only: bool = False, same_site: Optional[str] = None,
                   expiry: Optional[int] = None, partition: Optional[Dict[str, Any]] = None) -> None:
        commands = self._require()
        cookie: Dict[str, Any] = {
            "name": name, "value": {"type": "string", "value": value},
            "domain": domain, "path": path, "secure": bool(secure), "httpOnly": bool(http_only),
        }
        if same_site:
            cookie["sameSite"] = same_site
        if expiry is not None:
            cookie["expiry"] = int(expiry)
        self._loop.run(commands.storage.set_cookie(cookie, partition=partition), timeout=10)

    def delete_cookies(self, *, name: Optional[str] = None, domain: Optional[str] = None,
                       partition: Optional[Dict[str, Any]] = None) -> None:
        commands = self._require()
        filter_: Dict[str, Any] = {}
        if name:
            filter_["name"] = name
        if domain:
            filter_["domain"] = domain
        self._loop.run(commands.storage.delete_cookies(filter=filter_ or None, partition=partition), timeout=10)

    # -- navigation & downloads (§7.3) ------------------------------------

    def wait_for_navigation(self, event: str, *, context: Optional[str] = None,
                            timeout: float = 10.0) -> Dict[str, Any]:
        method = event if event.startswith("browsingContext.") else f"browsingContext.{event}"
        if method not in self._subscribed:
            self.subscribe([method])

        def predicate(params: Dict[str, Any]) -> bool:
            return context is None or params.get("context") == context

        buffered = self._buffers.buffer(method).get(predicate=predicate)
        if buffered:
            return buffered[-1]
        return self._loop.run(self._wait_event((method,), predicate, timeout), timeout=timeout + 1)

    def get_navigation_events(self, event: str) -> List[Dict[str, Any]]:
        method = event if event.startswith("browsingContext.") else f"browsingContext.{event}"
        return self._buffers.buffer(method).get()

    def set_download_behavior(self, *, behavior: str = "allowed",
                              destination_folder: Optional[str] = None) -> None:
        commands = self._require()
        self._run_gated("browser.setDownloadBehavior", commands.browser.set_download_behavior(
            behavior=behavior, destination_folder=destination_folder), 10)

    def support_matrix(self) -> Dict[str, Any]:
        """Return the capability support matrix + tested-against versions."""
        return {"tested_against": support.TESTED_AGAINST, "support": support.SUPPORT}

    def wait_for_download(self, *, timeout: float = 30.0) -> Dict[str, Any]:
        if "browsingContext.downloadEnd" not in self._subscribed:
            self.subscribe(["browsingContext.downloadEnd"])
        buffered = self._buffers.buffer("browsingContext.downloadEnd").get()
        if buffered:
            return buffered[-1]
        return self._loop.run(
            self._wait_event(("browsingContext.downloadEnd",), lambda p: True, timeout), timeout=timeout + 1)

    def clear_buffers(self) -> None:
        self._buffers.clear()

    # -- diagnostics ------------------------------------------------------

    def dropped_event_count(self) -> int:
        return self._buffers.dropped_total
