# Copyright 2026 MarketSquare
# Licensed under the Apache License, Version 2.0 (the "License").
"""bidi-init installer: offline status + helpers (no network)."""
from bidi_core import installer


def test_mapper_status_ok():
    ok, size = installer._mapper_status()
    assert ok is True and size > 100_000  # vendored bundle present & valid


def test_status_returns_zero_when_mapper_ok(capsys):
    rc = installer.main([])  # default = status, no downloads
    out = capsys.readouterr().out
    assert rc == 0 and "bundled mapper" in out and "OK" in out


def test_drivers_optin_message_no_download(capsys):
    rc = installer.main(["--drivers", "chromedriver"])
    out = capsys.readouterr().out
    assert rc == 0 and "optional" in out.lower()
