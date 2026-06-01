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
"""Playwright page <-> BiDi browsing-context correlation (design.md D6).

The matching logic is pure (tree-in, context-id-out) so it can be unit-tested
without a live browser. The plugin feeds it a target id + URL read from the
Playwright side (via the bundled ``helper.js`` jsextension) and the BiDi
``browsingContext.getTree`` result.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def flatten_contexts(tree: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Depth-first flatten of a ``browsingContext.getTree`` ``contexts`` list."""
    flat: List[Dict[str, Any]] = []
    for node in tree:
        flat.append(node)
        children = node.get("children") or []
        if children:
            flat.extend(flatten_contexts(children))
    return flat


def match_context(
    tree: List[Dict[str, Any]],
    *,
    target_id: Optional[str] = None,
    url: Optional[str] = None,
) -> Optional[str]:
    """Resolve a BiDi context id from a getTree result.

    Preference order (design.md D6):
      1. Match by target id where the transport aligns it with the context id
         (Chromium under the mapper).
      2. Fall back to URL plus creation order (first matching context in
         depth-first / creation order).
    """
    contexts = flatten_contexts(tree)

    if target_id:
        for context in contexts:
            # Under the Chromium mapper the BiDi ``context`` id equals the CDP
            # target id; some transports also echo it as ``targetId``.
            if context.get("context") == target_id or context.get("targetId") == target_id:
                return context.get("context")

    if url:
        for context in contexts:
            if context.get("url") == url:
                return context.get("context")

    return None


class CorrelationCache:
    """Caches page-key -> context-id, refreshed on navigation (design.md D6)."""

    def __init__(self) -> None:
        self._by_key: Dict[str, str] = {}

    def get(self, page_key: str) -> Optional[str]:
        return self._by_key.get(page_key)

    def put(self, page_key: str, context_id: str) -> None:
        self._by_key[page_key] = context_id

    def invalidate(self, page_key: str) -> None:
        self._by_key.pop(page_key, None)

    def clear(self) -> None:
        self._by_key.clear()
