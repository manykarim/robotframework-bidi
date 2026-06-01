# Copyright 2026 MarketSquare
# Licensed under the Apache License, Version 2.0 (the "License").
"""Capability gating: fail-fast precheck + runtime error translation."""

import pytest

from bidi_core.bidi_client import BiDiError
from bidi_core import support
from tests.test_manager import make_manager


def test_known_unsupported_fails_fast_without_round_trip():
    manager, fake = make_manager()
    manager.connect("ws://x", browser="chromium")
    with pytest.raises(BiDiError) as exc:
        manager.set_forced_colors("dark", context="C1")  # matrix: chromium False
    assert "not supported on chromium" in str(exc.value)
    # fail-fast: the command was never sent
    assert "emulation.setForcedColorsModeThemeOverride" not in [m for m, _ in fake.sent]
    manager.disconnect()


def test_runtime_unsupported_error_is_translated():
    manager, fake = make_manager(
        {"emulation.setUserAgentOverride": BiDiError("unsupported operation: Method ... wasn't found")})
    manager.connect("ws://x", browser="firefox")
    with pytest.raises(BiDiError) as exc:
        manager.set_user_agent("UA", context="C1")  # matrix: None -> attempt -> translate
    assert "not supported on firefox" in str(exc.value)
    manager.disconnect()


def test_supported_command_runs():
    manager, fake = make_manager()
    manager.connect("ws://x", browser="chromium")
    manager.set_locale("de-DE", context="C1")  # matrix: chromium True
    assert "emulation.setLocaleOverride" in [m for m, _ in fake.sent]
    manager.disconnect()


def test_support_helpers():
    assert support.is_supported("emulation.setLocaleOverride", "chrome") is True
    assert support.is_supported("emulation.setForcedColorsModeThemeOverride", "chromium") is False
    assert support.is_supported("emulation.setUserAgentOverride", "firefox") is None
    assert support.normalize_engine("msedge") == "chromium"
    assert support.is_unsupported_error("unsupported operation: foo")
