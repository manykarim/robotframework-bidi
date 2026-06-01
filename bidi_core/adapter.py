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
"""Host adapter contract (design.md D1).

The core is framework-neutral; the two host-specific concerns are isolated here:

1. **Correlation** — resolving the host's *current page* to BiDi correlation
   hints (a CDP target id and/or a URL). The Browser adapter reads these from a
   bundled jsextension; a Selenium adapter reads them from the WebDriver.
2. **Launch** (optional) — starting a BiDi-reachable browser. The neutral
   helpers in :mod:`bidi_core.launcher` cover the common cases; an adapter may
   wrap them or provide its own.

A host implements :class:`HostAdapter` (or just supplies a ``page_ref`` callable)
so the same :class:`bidi_core.manager.BiDiManager` backs multiple test libraries.
"""

from __future__ import annotations

from typing import Callable, Optional, Protocol, TypedDict, runtime_checkable


class PageRef(TypedDict, total=False):
    """Correlation hints for the host's current page."""

    target_id: Optional[str]
    url: Optional[str]


@runtime_checkable
class HostAdapter(Protocol):
    """Minimal contract a host test library implements to back the core."""

    def current_page_ref(self) -> PageRef:
        """Return correlation hints (``target_id`` and/or ``url``) for the
        host's currently active page. Either field may be ``None``; the core
        prefers ``target_id`` and falls back to ``url`` (see
        :func:`bidi_core.correlation.match_context`)."""
        ...


# A plain callable is also accepted anywhere a HostAdapter is, for adapters that
# don't need a class.
PageRefProvider = Callable[[], PageRef]


def as_page_ref(target_id: Optional[str] = None, url: Optional[str] = None) -> PageRef:
    """Build a :class:`PageRef` from optional hints."""
    return {"target_id": target_id, "url": url}
