#!/usr/bin/env python3
# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Phase 0 runner (Chromium): launch a BiDi+CDP Chromium via chromedriver and run
the spike. Validates tasks 1.1-1.3 and 1.5 (coexistence). Requires chromedriver
on PATH. Run: ``python spike/run_phase0_chromium.py``"""
import asyncio
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Browser_BiDi.launcher import launch_chromium
from spike.bidi_spike import run

NAV_URL = "https://example.com/"


def main() -> int:
    print("[phase0] launching Chromium via chromedriver (headless)...", flush=True)
    browser = None
    rc = 1
    try:
        browser = launch_chromium(
            port=9591, headless=True, extra_args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        print(f"[phase0] BiDi  = {browser.bidi_url}", flush=True)
        print(f"[phase0] CDP   = {browser.cdp_url}  (coexists with BiDi -> task 1.5)", flush=True)
        rc = asyncio.run(asyncio.wait_for(run(browser.bidi_url, NAV_URL, ""), timeout=45))
    except Exception:
        print("[phase0] ERROR:\n" + traceback.format_exc(), flush=True)
        rc = 2
    finally:
        if browser is not None:
            browser.close()
            print("[phase0] browser+driver closed", flush=True)
    print(f"[phase0] exit rc={rc}", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
