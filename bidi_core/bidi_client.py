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
"""Thin WebDriver BiDi client.

Scoped intentionally to the ``session``/``network``/``log``/``script``/
``browsingContext`` modules actually used by the extension. The protocol is
pre-final, so a small surface is cheaper to keep correct than tracking a
general-purpose dependency. The concrete client sits behind the
:class:`BiDiClient` interface so it can be swapped for a third-party client
later (see design.md, decision D3).
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, List, Optional

EventCallback = Callable[[Dict[str, Any]], None]


class BiDiError(Exception):
    """A BiDi command returned an ``error`` response, or the transport failed."""

    def __init__(self, error: str, message: str = "", *, command: str = "") -> None:
        self.error = error
        self.message = message
        self.command = command
        detail = f"{error}: {message}" if message else error
        if command:
            detail = f"{command} -> {detail}"
        super().__init__(detail)


class BiDiClient(ABC):
    """Swappable BiDi client interface (design.md D3).

    Implementations own a single WebSocket connection and translate
    request/response into awaitable command calls plus pushed events.
    """

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def send_command(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]: ...

    @abstractmethod
    def add_event_listener(self, method: str, callback: EventCallback) -> None: ...

    @abstractmethod
    def remove_event_listener(self, method: str, callback: EventCallback) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...


# A duplex transport is anything exposing async ``send(str)`` / ``recv() -> str``
# / ``close()``. ``websockets`` client connections satisfy this directly; tests
# inject a fake in-memory duplex so the client logic runs without a browser.
Connector = Callable[[], Awaitable[Any]]


class WebsocketsBiDiClient(BiDiClient):
    """JSON-RPC duplex over a WebSocket with an id -> Future correlation map.

    A single background reader coroutine drains the socket: responses resolve
    the pending Future for their ``id``; events are dispatched to registered
    listeners by ``method`` name.
    """

    def __init__(self, url: str, *, connector: Optional[Connector] = None) -> None:
        self._url = url
        self._connector = connector
        self._ws: Any = None
        self._next_id = 0
        self._pending: Dict[int, "asyncio.Future[Dict[str, Any]]"] = {}
        self._listeners: Dict[str, List[EventCallback]] = {}
        self._reader: Optional[asyncio.Task] = None
        self._closed = False

    async def connect(self) -> None:
        if self._connector is not None:
            self._ws = await self._connector()
        else:
            # Imported lazily so the module (and its unit tests) load without
            # the optional ``websockets`` dependency present.
            import websockets

            self._ws = await websockets.connect(self._url, max_size=None)
        self._reader = asyncio.ensure_future(self._read_loop())

    async def send_command(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self._closed:
            raise BiDiError("connection closed", "client is not connected", command=method)
        self._next_id += 1
        command_id = self._next_id
        loop = asyncio.get_event_loop()
        future: "asyncio.Future[Dict[str, Any]]" = loop.create_future()
        self._pending[command_id] = future
        message = {"id": command_id, "method": method, "params": params or {}}
        await self._ws.send(json.dumps(message))
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
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - teardown is best-effort
                pass
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001 - socket may already be gone
                pass
        # Fail any in-flight commands so blocked keywords don't hang forever.
        for future in self._pending.values():
            if not future.done():
                future.set_exception(BiDiError("connection closed", "client closed while awaiting response"))
        self._pending.clear()

    async def _read_loop(self) -> None:
        try:
            while True:
                raw = await self._ws.recv()
                self._dispatch(json.loads(raw))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface transport death to waiters
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(BiDiError("transport error", str(exc)))
            self._pending.clear()

    def _dispatch(self, message: Dict[str, Any]) -> None:
        """Route one decoded BiDi message. Pure given ``self`` state -> unit-tested."""
        message_id = message.get("id")
        if message_id is not None:
            future = self._pending.pop(message_id, None)
            if future is None or future.done():
                return
            # BiDi errors are {"type":"error","error":"...","message":"..."};
            # a CDP endpoint (e.g. Chrome's /devtools/browser socket, which is
            # NOT BiDi) replies {"error":{"code","message"}}. Detect both so a
            # wrong endpoint fails loudly instead of looking like an empty success.
            if message.get("type") == "error" or "error" in message:
                err = message.get("error")
                if isinstance(err, dict):
                    future.set_exception(
                        BiDiError(str(err.get("code", "error")), err.get("message", ""))
                    )
                else:
                    future.set_exception(
                        BiDiError(err or "unknown error", message.get("message", ""))
                    )
            else:
                future.set_result(message.get("result", {}))
            return
        # No id -> an event. BiDi tags events with ``type: "event"`` and a
        # ``method`` such as ``log.entryAdded``.
        method = message.get("method")
        if not method:
            return
        for callback in list(self._listeners.get(method, [])):
            callback(message.get("params", {}))
