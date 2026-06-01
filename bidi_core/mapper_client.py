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
"""Driverless BiDi for Chrome via the chromium-bidi mapper, over CDP.

Chrome's ``--remote-debugging-port`` socket speaks CDP, not BiDi. This client
reproduces what chromedriver does internally: it loads the **chromium-bidi
mapper** (a JS bundle) into a hidden Chrome tab over CDP, then proxies BiDi
messages in/out of that tab — so NO chromedriver and NO Node are required.

Bootstrap (chromedriver-style, from chromium-bidi ``MapperCdpConnection``):
  1. ``Target.attachToBrowserTarget``                       -> browser session
  2. ``Target.createTarget`` about:blank#MAPPER (hidden)    -> mapper target id
  3. ``Target.attachToTarget`` flatten                      -> mapper session
  4. ``Runtime.enable``
  5. ``Target.exposeDevToolsProtocol`` bindingName=cdp      -> window.cdp in tab
  6. ``Runtime.addBinding`` name=sendBidiResponse           -> outbound channel
  7. ``Runtime.evaluate`` <mapper bundle>
  8. ``Runtime.evaluate`` window.runMapperInstance('<targetId>')
Send BiDi:  Runtime.evaluate ``onBidiMessage("<json>")`` (double-encoded).
Recv BiDi:  Runtime.bindingCalled events with name=sendBidiResponse.

It implements the same :class:`BiDiClient` interface as the WebSocket client, so
the rest of the extension is unchanged.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .bidi_client import BiDiClient, BiDiError, EventCallback

DEFAULT_MAPPER = Path(__file__).parent / "mapper" / "mapperTab.js"
Connector = Callable[[], Awaitable[Any]]


def load_mapper_source(path: Optional[Path] = None) -> str:
    return (path or DEFAULT_MAPPER).read_text(encoding="utf-8")


class MapperBiDiClient(BiDiClient):
    """BiDi client that proxies through the chromium-bidi mapper over CDP."""

    def __init__(
        self,
        cdp_url: str,
        *,
        mapper_source: Optional[str] = None,
        connector: Optional[Connector] = None,
    ) -> None:
        self._cdp_url = cdp_url
        self._mapper_source = mapper_source if mapper_source is not None else load_mapper_source()
        self._connector = connector
        self._ws: Any = None
        self._reader: Optional[asyncio.Task] = None
        self._closed = False
        # CDP layer (transport to the browser)
        self._cdp_id = 0
        self._cdp_pending: Dict[int, "asyncio.Future[Dict[str, Any]]"] = {}
        # BiDi layer (messages proxied through the mapper tab)
        self._bidi_id = 0
        self._bidi_pending: Dict[int, "asyncio.Future[Dict[str, Any]]"] = {}
        self._listeners: Dict[str, List[EventCallback]] = {}
        self._mapper_session: Optional[str] = None

    # -- BiDiClient interface --------------------------------------------

    async def connect(self) -> None:
        if self._connector is not None:
            self._ws = await self._connector()
        else:
            import websockets

            self._ws = await websockets.connect(self._cdp_url, max_size=None)
        self._reader = asyncio.ensure_future(self._read_loop())
        await self._bootstrap_mapper()

    async def send_command(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self._closed or self._mapper_session is None:
            raise BiDiError("connection closed", "mapper client is not connected", command=method)
        self._bidi_id += 1
        bidi_id = self._bidi_id
        loop = asyncio.get_event_loop()
        future: "asyncio.Future[Dict[str, Any]]" = loop.create_future()
        self._bidi_pending[bidi_id] = future
        command = {"id": bidi_id, "method": method, "params": params or {}}
        # Double-encode: JSON of the command, then embed as a JS string literal.
        expression = "onBidiMessage(" + json.dumps(json.dumps(command)) + ")"
        await self._cdp("Runtime.evaluate", {"expression": expression}, session=self._mapper_session)
        return await future

    def add_event_listener(self, method: str, callback: EventCallback) -> None:
        self._listeners.setdefault(method, []).append(callback)

    def remove_event_listener(self, method: str, callback: EventCallback) -> None:
        listeners = self._listeners.get(method)
        if listeners and callback in listeners:
            listeners.remove(callback)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._reader is not None:
            self._reader.cancel()
            try:
                await self._reader
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass
        for future in list(self._cdp_pending.values()) + list(self._bidi_pending.values()):
            if not future.done():
                future.set_exception(BiDiError("connection closed", "client closed"))
        self._cdp_pending.clear()
        self._bidi_pending.clear()

    # -- CDP layer --------------------------------------------------------

    async def _cdp(
        self, method: str, params: Optional[Dict[str, Any]] = None, *, session: Optional[str] = None
    ) -> Dict[str, Any]:
        self._cdp_id += 1
        cdp_id = self._cdp_id
        loop = asyncio.get_event_loop()
        future: "asyncio.Future[Dict[str, Any]]" = loop.create_future()
        self._cdp_pending[cdp_id] = future
        message: Dict[str, Any] = {"id": cdp_id, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        await self._ws.send(json.dumps(message))
        return await future

    async def _read_loop(self) -> None:
        try:
            while True:
                self._dispatch_cdp(json.loads(await self._ws.recv()))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            for future in list(self._cdp_pending.values()) + list(self._bidi_pending.values()):
                if not future.done():
                    future.set_exception(BiDiError("transport error", str(exc)))

    def _dispatch_cdp(self, message: Dict[str, Any]) -> None:
        cdp_id = message.get("id")
        if cdp_id is not None:
            future = self._cdp_pending.pop(cdp_id, None)
            if future is None or future.done():
                return
            if "error" in message:
                err = message["error"]
                future.set_exception(BiDiError(str(err.get("code", "cdp error")), err.get("message", "")))
            else:
                future.set_result(message.get("result", {}))
            return
        # CDP event. The only one we care about is the mapper's outbound binding.
        if message.get("method") == "Runtime.bindingCalled":
            params = message.get("params", {})
            if params.get("name") == "sendBidiResponse":
                self._handle_bidi_payload(params.get("payload", ""))

    def _handle_bidi_payload(self, payload: str) -> None:
        try:
            msg = json.loads(payload)
        except (ValueError, TypeError):
            return
        msg_type = msg.get("type")
        msg_id = msg.get("id")
        if msg_id is not None and msg_type in ("success", "error"):
            future = self._bidi_pending.pop(msg_id, None)
            if future is None or future.done():
                return
            if msg_type == "error":
                future.set_exception(BiDiError(msg.get("error", "unknown error"), msg.get("message", "")))
            else:
                future.set_result(msg.get("result", {}))
            return
        if msg_type == "event":
            method = msg.get("method")
            for callback in list(self._listeners.get(method, [])):
                callback(msg.get("params", {}))

    # -- mapper bootstrap -------------------------------------------------

    async def _bootstrap_mapper(self) -> None:
        browser_session = (await self._cdp("Target.attachToBrowserTarget"))["sessionId"]
        try:
            created = await self._cdp(
                "Target.createTarget",
                {"url": "about:blank#MAPPER_TARGET", "hidden": True, "background": True},
                session=browser_session,
            )
        except BiDiError:
            # Older Chrome may reject hidden/background params.
            created = await self._cdp(
                "Target.createTarget", {"url": "about:blank"}, session=browser_session
            )
        mapper_target = created["targetId"]
        self._mapper_session = (
            await self._cdp(
                "Target.attachToTarget",
                {"targetId": mapper_target, "flatten": True},
                session=browser_session,
            )
        )["sessionId"]
        await self._cdp("Runtime.enable", session=self._mapper_session)
        await self._cdp(
            "Target.exposeDevToolsProtocol",
            {"bindingName": "cdp", "targetId": mapper_target, "inheritPermissions": True},
            session=browser_session,
        )
        await self._cdp("Runtime.addBinding", {"name": "sendBidiResponse"}, session=self._mapper_session)
        await self._cdp("Runtime.evaluate", {"expression": self._mapper_source}, session=self._mapper_session)
        await self._cdp(
            "Runtime.evaluate",
            {"expression": f"window.runMapperInstance('{mapper_target}')", "awaitPromise": True},
            session=self._mapper_session,
        )
