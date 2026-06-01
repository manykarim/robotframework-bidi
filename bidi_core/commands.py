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
"""Typed wrappers for the BiDi commands the extension actually issues.

These keep BiDi method names and param shapes in one place so the rest of the
code is decoupled from raw protocol strings. Only the ``session``/``network``/
``log``/``script``/``browsingContext`` modules are covered (design.md D3).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .bidi_client import BiDiClient

# Event method names grouped by module, used for subscription validation and
# to enumerate the buffers the plugin maintains.
NETWORK_EVENTS = (
    "network.beforeRequestSent",
    "network.responseStarted",
    "network.responseCompleted",
    "network.fetchError",
)
LOG_EVENTS = ("log.entryAdded",)
SCRIPT_EVENTS = ("script.realmCreated", "script.realmDestroyed")
NAVIGATION_EVENTS = (
    "browsingContext.navigationStarted",
    "browsingContext.domContentLoaded",
    "browsingContext.load",
    "browsingContext.navigationFailed",
    "browsingContext.fragmentNavigated",
    "browsingContext.historyUpdated",
)
DOWNLOAD_EVENTS = ("browsingContext.downloadWillBegin", "browsingContext.downloadEnd")
INPUT_EVENTS = ("input.fileDialogOpened",)
# Events the manager registers buffering listeners for (buffered iff subscribed).
ALL_KNOWN_EVENTS = (
    NETWORK_EVENTS + LOG_EVENTS + SCRIPT_EVENTS
    + NAVIGATION_EVENTS + DOWNLOAD_EVENTS + INPUT_EVENTS
)


class SessionModule:
    def __init__(self, client: BiDiClient) -> None:
        self._client = client

    async def new(self, capabilities: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._client.send_command("session.new", {"capabilities": capabilities or {}})

    async def status(self) -> Dict[str, Any]:
        return await self._client.send_command("session.status")

    async def subscribe(self, events: List[str], contexts: Optional[List[str]] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"events": events}
        if contexts:
            params["contexts"] = contexts
        return await self._client.send_command("session.subscribe", params)

    async def unsubscribe(self, events: List[str], contexts: Optional[List[str]] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"events": events}
        if contexts:
            params["contexts"] = contexts
        return await self._client.send_command("session.unsubscribe", params)


class NetworkModule:
    def __init__(self, client: BiDiClient) -> None:
        self._client = client

    async def add_data_collector(
        self,
        *,
        data_types: Optional[List[str]] = None,
        max_encoded_data_size: int = 20_000_000,
        contexts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Register a collector so response bodies are retained for later getData.

        Without a collector Chrome does not keep response bodies and getData
        fails with "No collected response data" (found via the Phase 0 spike).
        Must be registered BEFORE the responses you want to read.
        """
        params: Dict[str, Any] = {
            "dataTypes": data_types or ["response"],
            "maxEncodedDataSize": max_encoded_data_size,
        }
        if contexts:
            params["contexts"] = contexts
        return await self._client.send_command("network.addDataCollector", params)

    async def remove_data_collector(self, collector: str) -> Dict[str, Any]:
        return await self._client.send_command(
            "network.removeDataCollector", {"collector": collector}
        )

    async def get_data(
        self, request_id: str, *, collector: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve a collected response body for ``request_id``.

        Uses ``network.getData`` against the response ``dataType`` (the BiDi
        response-body retrieval entry point). Requires a data collector to have
        been registered before the response (see :meth:`add_data_collector`).
        """
        params: Dict[str, Any] = {"request": request_id, "dataType": "response"}
        if collector:
            params["collector"] = collector
        return await self._client.send_command("network.getData", params)

    # -- interception (§7.5.3, §7.5.5) ------------------------------------

    async def add_intercept(
        self, phases: List[str], url_patterns: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"phases": phases}
        if url_patterns:
            params["urlPatterns"] = url_patterns
        return await self._client.send_command("network.addIntercept", params)

    async def remove_intercept(self, intercept: str) -> Dict[str, Any]:
        return await self._client.send_command("network.removeIntercept", {"intercept": intercept})

    async def continue_request(
        self, request: str, *, headers: Optional[List[Dict[str, Any]]] = None,
        method: Optional[str] = None, body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"request": request}
        if headers:
            params["headers"] = headers
        if method:
            params["method"] = method
        if body:
            params["body"] = body
        return await self._client.send_command("network.continueRequest", params)

    async def continue_response(self, request: str) -> Dict[str, Any]:
        return await self._client.send_command("network.continueResponse", {"request": request})

    async def provide_response(
        self, request: str, *, status_code: int = 200, reason_phrase: Optional[str] = None,
        headers: Optional[List[Dict[str, Any]]] = None, body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"request": request, "statusCode": status_code}
        if reason_phrase:
            params["reasonPhrase"] = reason_phrase
        if headers:
            params["headers"] = headers
        if body:
            params["body"] = body
        return await self._client.send_command("network.provideResponse", params)

    async def fail_request(self, request: str) -> Dict[str, Any]:
        return await self._client.send_command("network.failRequest", {"request": request})

    async def continue_with_auth(
        self, request: str, *, action: str = "provideCredentials",
        username: Optional[str] = None, password: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"request": request, "action": action}
        if action == "provideCredentials":
            params["credentials"] = {"type": "password", "username": username or "", "password": password or ""}
        return await self._client.send_command("network.continueWithAuth", params)

    async def set_cache_behavior(
        self, cache_behavior: str, contexts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"cacheBehavior": cache_behavior}
        if contexts:
            params["contexts"] = contexts
        return await self._client.send_command("network.setCacheBehavior", params)


class ScriptModule:
    def __init__(self, client: BiDiClient) -> None:
        self._client = client

    async def evaluate(
        self,
        expression: str,
        target: Dict[str, Any],
        *,
        await_promise: bool = True,
    ) -> Dict[str, Any]:
        return await self._client.send_command(
            "script.evaluate",
            {"expression": expression, "target": target, "awaitPromise": await_promise},
        )

    async def call_function(
        self,
        function_declaration: str,
        target: Dict[str, Any],
        *,
        arguments: Optional[List[Dict[str, Any]]] = None,
        await_promise: bool = True,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "functionDeclaration": function_declaration,
            "target": target,
            "awaitPromise": await_promise,
            "arguments": arguments or [],
        }
        return await self._client.send_command("script.callFunction", params)

    async def add_preload_script(
        self, function_declaration: str, *, sandbox: Optional[str] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"functionDeclaration": function_declaration}
        if sandbox:
            params["sandbox"] = sandbox
        return await self._client.send_command("script.addPreloadScript", params)


class BrowsingContextModule:
    def __init__(self, client: BiDiClient) -> None:
        self._client = client

    async def get_tree(self) -> Dict[str, Any]:
        return await self._client.send_command("browsingContext.getTree")

    async def locate_nodes(
        self,
        context: str,
        locator: Dict[str, Any],
        *,
        max_node_count: Optional[int] = None,
        start_nodes: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"context": context, "locator": locator}
        if max_node_count is not None:
            params["maxNodeCount"] = max_node_count
        if start_nodes:
            params["startNodes"] = start_nodes
        return await self._client.send_command("browsingContext.locateNodes", params)

    async def capture_screenshot(
        self,
        context: str,
        *,
        origin: Optional[str] = None,
        clip: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"context": context}
        if origin:
            params["origin"] = origin
        if clip:
            params["clip"] = clip
        return await self._client.send_command("browsingContext.captureScreenshot", params)

    async def create(
        self, *, type: str = "tab", user_context: Optional[str] = None,
        reference_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"type": type}
        if user_context:
            params["userContext"] = user_context
        if reference_context:
            params["referenceContext"] = reference_context
        return await self._client.send_command("browsingContext.create", params)

    async def set_viewport(
        self, context: str, *, width: int, height: int,
        device_pixel_ratio: Optional[float] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"context": context, "viewport": {"width": width, "height": height}}
        if device_pixel_ratio is not None:
            params["devicePixelRatio"] = device_pixel_ratio
        return await self._client.send_command("browsingContext.setViewport", params)


class StorageModule:
    def __init__(self, client: BiDiClient) -> None:
        self._client = client

    async def get_cookies(
        self, *, filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if filter:
            params["filter"] = filter
        return await self._client.send_command("storage.getCookies", params)

    async def set_cookie(
        self, cookie: Dict[str, Any], *, partition: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"cookie": cookie}
        if partition:
            params["partition"] = partition
        return await self._client.send_command("storage.setCookie", params)

    async def delete_cookies(
        self, *, filter: Optional[Dict[str, Any]] = None, partition: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if filter:
            params["filter"] = filter
        if partition:
            params["partition"] = partition
        return await self._client.send_command("storage.deleteCookies", params)


class EmulationModule:
    """BiDi emulation overrides (§7.4). Several commands are recent in the
    Editor's Draft and unevenly implemented — capability-gated at the keyword
    layer (see the support matrix)."""

    def __init__(self, client: BiDiClient) -> None:
        self._client = client

    async def _override(self, method: str, body: Dict[str, Any], contexts, user_contexts) -> Dict[str, Any]:
        params = dict(body)
        if contexts:
            params["contexts"] = contexts
        if user_contexts:
            params["userContexts"] = user_contexts
        return await self._client.send_command(method, params)

    async def set_geolocation(self, *, latitude: float, longitude: float, accuracy: float = 1.0,
                              contexts=None, user_contexts=None) -> Dict[str, Any]:
        coords = {"latitude": latitude, "longitude": longitude, "accuracy": accuracy}
        return await self._override("emulation.setGeolocationOverride",
                                    {"coordinates": coords}, contexts, user_contexts)

    async def set_locale(self, locale: Optional[str], *, contexts=None, user_contexts=None) -> Dict[str, Any]:
        return await self._override("emulation.setLocaleOverride", {"locale": locale}, contexts, user_contexts)

    async def set_timezone(self, timezone: Optional[str], *, contexts=None, user_contexts=None) -> Dict[str, Any]:
        return await self._override("emulation.setTimezoneOverride", {"timezone": timezone}, contexts, user_contexts)

    async def set_user_agent(self, user_agent: Optional[str], *, contexts=None, user_contexts=None) -> Dict[str, Any]:
        return await self._override("emulation.setUserAgentOverride", {"userAgent": user_agent}, contexts, user_contexts)

    async def set_forced_colors(self, theme: Optional[str], *, contexts=None, user_contexts=None) -> Dict[str, Any]:
        return await self._override("emulation.setForcedColorsModeThemeOverride", {"theme": theme}, contexts, user_contexts)

    async def set_scripting_enabled(self, enabled: Optional[bool], *, contexts=None, user_contexts=None) -> Dict[str, Any]:
        return await self._override("emulation.setScriptingEnabled", {"enabled": enabled}, contexts, user_contexts)

    async def set_screen_orientation(self, natural: str, type_: str, *, contexts=None, user_contexts=None) -> Dict[str, Any]:
        return await self._override("emulation.setScreenOrientationOverride",
                                    {"screenOrientation": {"natural": natural, "type": type_}}, contexts, user_contexts)


class InputModule:
    """`input` module (§7.9) — Actions API and file uploads."""

    def __init__(self, client: BiDiClient) -> None:
        self._client = client

    async def perform_actions(self, context: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        return await self._client.send_command(
            "input.performActions", {"context": context, "actions": actions})

    async def release_actions(self, context: str) -> Dict[str, Any]:
        return await self._client.send_command("input.releaseActions", {"context": context})

    async def set_files(self, context: str, element: Dict[str, Any], files: List[str]) -> Dict[str, Any]:
        return await self._client.send_command(
            "input.setFiles", {"context": context, "element": element, "files": files})


class BrowserModule:
    """`browser` module (§7.2) — user contexts for isolation; downloads."""

    def __init__(self, client: BiDiClient) -> None:
        self._client = client

    async def create_user_context(self) -> Dict[str, Any]:
        return await self._client.send_command("browser.createUserContext", {})

    async def remove_user_context(self, user_context: str) -> Dict[str, Any]:
        return await self._client.send_command("browser.removeUserContext", {"userContext": user_context})

    async def set_download_behavior(
        self, *, behavior: str = "allowed", destination_folder: Optional[str] = None,
        user_contexts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        download: Dict[str, Any] = {"type": behavior}
        if destination_folder:
            download["destinationFolder"] = destination_folder
        params: Dict[str, Any] = {"downloadBehavior": download}
        if user_contexts:
            params["userContexts"] = user_contexts
        return await self._client.send_command("browser.setDownloadBehavior", params)


class Commands:
    """Bundle of the module wrappers bound to a single client."""

    def __init__(self, client: BiDiClient) -> None:
        self.session = SessionModule(client)
        self.network = NetworkModule(client)
        self.script = ScriptModule(client)
        self.browsing_context = BrowsingContextModule(client)
        self.storage = StorageModule(client)
        self.emulation = EmulationModule(client)
        self.browser = BrowserModule(client)
        self.input = InputModule(client)
