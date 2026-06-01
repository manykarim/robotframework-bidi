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
"""Bounded, per-event-class buffers (design.md D5).

Each stored event gets a monotonically increasing sequence number so callers
can drain incrementally with a ``since`` marker. Overflow drops the oldest
event (``deque(maxlen=N)``) and is *observable* via :attr:`EventBuffer.dropped`
rather than silently unbounded.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple


class EventBuffer:
    """A bounded FIFO of events for a single BiDi event class."""

    def __init__(self, maxlen: int) -> None:
        self._items: Deque[Tuple[int, Dict[str, Any]]] = deque(maxlen=maxlen)
        self._seq = 0
        self.dropped = 0

    def append(self, event: Dict[str, Any]) -> int:
        if self._items.maxlen and len(self._items) == self._items.maxlen:
            # deque will evict the oldest on append; record it so truncation is
            # never silent.
            self.dropped += 1
        self._seq += 1
        self._items.append((self._seq, event))
        return self._seq

    def latest_seq(self) -> int:
        return self._seq

    def get(
        self,
        *,
        since: Optional[int] = None,
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """Return buffered events newer than ``since`` matching ``predicate``."""
        result: List[Dict[str, Any]] = []
        for seq, event in self._items:
            if since is not None and seq <= since:
                continue
            if predicate is not None and not predicate(event):
                continue
            result.append(event)
        return result

    def clear(self) -> None:
        self._items.clear()


class EventBuffers:
    """Lazily-created :class:`EventBuffer` per event class, sharing a max size."""

    def __init__(self, maxlen: int = 1000) -> None:
        self._maxlen = maxlen
        self._buffers: Dict[str, EventBuffer] = {}

    def buffer(self, event_class: str) -> EventBuffer:
        if event_class not in self._buffers:
            self._buffers[event_class] = EventBuffer(self._maxlen)
        return self._buffers[event_class]

    def append(self, event_class: str, event: Dict[str, Any]) -> int:
        return self.buffer(event_class).append(event)

    def clear(self) -> None:
        for buffer in self._buffers.values():
            buffer.clear()

    @property
    def dropped_total(self) -> int:
        return sum(buffer.dropped for buffer in self._buffers.values())
