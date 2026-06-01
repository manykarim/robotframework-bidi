# Copyright 2026 MarketSquare
# Licensed under the Apache License, Version 2.0 (the "License").
"""Browser_BiDi re-export shims still resolve after the bidi_core extraction."""

def test_browser_bidi_shims_reexport_core():
    from Browser_BiDi.manager import BiDiManager
    from Browser_BiDi.bidi_client import BiDiError, WebsocketsBiDiClient
    from Browser_BiDi.launcher import launch_firefox, launch_chromium_driverless
    from Browser_BiDi.serialization import compute_timing
    from Browser_BiDi import BiDiManager as M2, BiDiError as E2
    import bidi_core
    assert BiDiManager is M2 is bidi_core.BiDiManager
    assert BiDiError is E2 is bidi_core.BiDiError
