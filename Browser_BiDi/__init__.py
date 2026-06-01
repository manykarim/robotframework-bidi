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
"""Browser-BiDi: the Robot Framework Browser adapter over :mod:`bidi_core`.

The BiDi engine now lives in :mod:`bidi_core` (framework-neutral). This package
is the Browser-library adapter (the ``BrowserBiDi`` plugin) and re-exports the
core's public API for backwards compatibility, so existing
``from Browser_BiDi.<module> import ...`` imports keep working.
"""

# Re-export the core API (back-compat). The plugin class ``BrowserBiDi`` lives in
# BrowserBiDi.py and imports the Browser library, so it is not re-exported here.
from bidi_core import (  # noqa: F401
    BiDiClient,
    BiDiError,
    BiDiManager,
    CorrelationCache,
    EventBuffer,
    EventBuffers,
    HostAdapter,
    PageRef,
    WebsocketsBiDiClient,
    flatten_contexts,
    match_context,
)

__version__ = "0.2.0"

__all__ = [
    "BiDiClient",
    "BiDiError",
    "WebsocketsBiDiClient",
    "EventBuffer",
    "EventBuffers",
    "CorrelationCache",
    "match_context",
    "flatten_contexts",
    "HostAdapter",
    "PageRef",
    "BiDiManager",
    "__version__",
]
