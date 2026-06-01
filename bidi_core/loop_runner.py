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
"""Dedicated asyncio loop on a background thread (design.md D4).

Robot keywords are synchronous; they push coroutines onto this loop with
``run_coroutine_threadsafe`` and block for the result, so the persistent
WebSocket and its subscriptions stay alive across keyword calls without
blocking Robot's main thread.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Awaitable, Optional, TypeVar

T = TypeVar("T")


class LoopRunner:
    """Owns an event loop running on its own daemon thread."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def running(self) -> bool:
        return self._loop is not None and self._loop.is_running()

    def start(self) -> None:
        if self.running:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run, name="BrowserBiDi-loop", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro: Awaitable[T], *, timeout: Optional[float] = None) -> T:
        """Run ``coro`` on the background loop and block for its result."""
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("BiDi event loop is not running; call Connect BiDi first")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def stop(self) -> None:
        """Stop the loop and join its thread. Best-effort and idempotent."""
        if self._loop is None:
            return
        loop = self._loop
        if loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        try:
            if not loop.is_closed():
                loop.close()
        except Exception:  # noqa: BLE001 - teardown is best-effort
            pass
        self._loop = None
        self._thread = None
