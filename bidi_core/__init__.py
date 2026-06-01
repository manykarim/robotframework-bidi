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
"""bidi_core: a library-agnostic WebDriver BiDi engine.

Depends only on a WebSocket library — it imports neither the Robot Framework
Browser library (Playwright) nor Selenium. Host test libraries provide a thin
adapter implementing :class:`bidi_core.adapter.HostAdapter` (page-correlation +
optional launch) and reuse this engine. See design.md decision D1.
"""

from .adapter import HostAdapter, PageRef
from .bidi_client import BiDiClient, BiDiError, WebsocketsBiDiClient
from .buffers import EventBuffer, EventBuffers
from .correlation import CorrelationCache, flatten_contexts, match_context
from .manager import BiDiManager

__version__ = "0.2.0"

__all__ = [
    "HostAdapter",
    "PageRef",
    "BiDiClient",
    "BiDiError",
    "WebsocketsBiDiClient",
    "EventBuffer",
    "EventBuffers",
    "CorrelationCache",
    "flatten_contexts",
    "match_context",
    "BiDiManager",
    "__version__",
]
