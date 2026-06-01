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
"""Per-engine BiDi capability support matrix and gating helpers (design.md D5).

WebDriver BiDi is a W3C Editor's Draft and control-side modules (`emulation`,
parts of `network`, downloads) are unevenly implemented across Chromium and
Firefox. This matrix is the single source of truth for capability gating: the
manager pre-checks known-unsupported commands (fail fast, no round-trip) and
translates runtime "unsupported operation" errors into the same actionable
message. Validated against the versions in TESTED_AGAINST; verify against your
own engines and keep this updated.
"""

from __future__ import annotations

from typing import Dict, Optional

# Spec revision + engine versions this matrix was validated against.
TESTED_AGAINST = {
    "bidi_spec": "W3C Editor's Draft 2026-05-11",
    "chromium": "Chrome 147 (chromium-bidi mapper 16.0.1)",
    "firefox": "Firefox 150 (native BiDi)",
}

# True = supported, False = known-unsupported, None = unknown (attempt + translate).
# Keyed by BiDi method, then normalized engine name ("chromium"/"firefox").
SUPPORT: Dict[str, Dict[str, Optional[bool]]] = {
    # network interception (validated on Chromium)
    "network.addIntercept": {"chromium": True, "firefox": None},
    "network.provideResponse": {"chromium": True, "firefox": None},
    "network.failRequest": {"chromium": True, "firefox": None},
    "network.continueRequest": {"chromium": True, "firefox": None},
    "network.continueWithAuth": {"chromium": True, "firefox": None},
    "network.setCacheBehavior": {"chromium": None, "firefox": None},
    # emulation
    "emulation.setLocaleOverride": {"chromium": True, "firefox": None},
    "emulation.setTimezoneOverride": {"chromium": True, "firefox": None},
    "emulation.setGeolocationOverride": {"chromium": True, "firefox": None},
    "emulation.setUserAgentOverride": {"chromium": True, "firefox": None},
    "emulation.setForcedColorsModeThemeOverride": {"chromium": False, "firefox": None},
    "emulation.setScriptingEnabled": {"chromium": False, "firefox": None},
    "emulation.setScreenOrientationOverride": {"chromium": None, "firefox": None},
    # viewport / contexts / input / downloads (validated on Chromium)
    "browsingContext.setViewport": {"chromium": True, "firefox": None},
    "browser.createUserContext": {"chromium": True, "firefox": True},
    "browser.setDownloadBehavior": {"chromium": True, "firefox": None},
    "input.performActions": {"chromium": True, "firefox": True},
    "input.setFiles": {"chromium": True, "firefox": True},
    "storage.setCookie": {"chromium": True, "firefox": True},
}

# Substrings that mark a BiDi error as "command not supported on this engine".
# Kept method-level specific to avoid mislabelling unrelated runtime errors
# (e.g. "no such element"/"no such node") as capability gaps. Only applied to
# the small set of gated control commands.
_UNSUPPORTED_MARKERS = ("unsupported operation", "no such command",
                        "unknown command", "wasn't found", "-32601")


def normalize_engine(browser: Optional[str]) -> Optional[str]:
    if not browser:
        return None
    b = browser.lower()
    if b in ("chromium", "chrome", "edge", "msedge", "chrome-headless-shell"):
        return "chromium"
    if b in ("firefox", "moz:firefox"):
        return "firefox"
    return b


def is_supported(method: str, browser: Optional[str]) -> Optional[bool]:
    """True/False/None (unknown) for a method on the given browser."""
    engine = normalize_engine(browser)
    entry = SUPPORT.get(method)
    if entry is None or engine is None:
        return None
    return entry.get(engine)


def is_unsupported_error(message: str) -> bool:
    msg = (message or "").lower()
    return any(marker in msg for marker in _UNSUPPORTED_MARKERS)


def unsupported_message(method: str, browser: Optional[str]) -> str:
    engine = normalize_engine(browser) or browser or "this browser"
    other = "Firefox" if engine == "chromium" else "Chrome"
    return (
        f"BiDi command '{method}' is not supported on {engine} "
        f"(WebDriver BiDi is a draft; engine support varies). "
        f"Try {other}, upgrade the browser, or check the support matrix "
        f"(bidi_core.support, validated against {TESTED_AGAINST.get(engine, 'tested engines')})."
    )
