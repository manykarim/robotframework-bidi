#!/usr/bin/env python3
# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Firefox Phase 0 + BiDi-level integration (task 1.4): validate the cross-browser
wins via the production BiDiManager against a geckodriver-launched Firefox.

NOTE (validated finding): full Strategy-1 coexistence (Playwright driving the
SAME Firefox) is NOT achievable through the Browser library today, because
Firefox has no CDP and Browser/Playwright cannot attach to an externally
launched Firefox -- it launches its own. So Firefox is validated at the BiDi
client level here (this harness drives navigation itself via BiDi). Response
bodies are best-effort (Firefox getData fails on compressed streams).
Requires geckodriver on PATH. Run: ``python spike/run_firefox.py``"""
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Browser_BiDi.launcher import launch_firefox
from Browser_BiDi.manager import BiDiManager

URL = "https://example.com/"
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" :: {detail}" if detail else ""), flush=True)


def main() -> int:
    browser = launch_firefox(port=4455, headless=True)
    print(f"[ff] bidi={browser.bidi_url}", flush=True)
    m = BiDiManager(buffer_size=200)
    try:
        m.connect(browser.bidi_url, browser="firefox",
                  auto_subscribe=["network.responseCompleted", "log.entryAdded"])
        check("connect + subscribe (FF)", m.connected)
        tree = m._loop.run(m._commands.browsing_context.get_tree(), timeout=10)
        ctx = tree["contexts"][0]["context"]
        m._loop.run(m._client.send_command(
            "browsingContext.navigate", {"context": ctx, "url": URL, "wait": "complete"}), timeout=30)
        m.evaluate("console.log('ff-marker'); 1", context=ctx)
        time.sleep(1)
        check("network events (FF)", len(m.get_network_events()) > 0)
        check("console log (FF)", any("ff-marker" in (l.get("text") or "") for l in m.get_console_log()))
        check("URL correlation (FF, no CDP target id)", m.context_for_page(url=URL) == ctx)
        check("BiDi Evaluate (FF)", m.evaluate("6*7", context=ctx) == 42)
        try:
            rid = next(e["request"]["request"] for e in m.get_network_events()
                       if e.get("request", {}).get("request"))
            body = m.get_response_body(rid)
            print(f"[ff] response body: {len(body)} chars (supported)", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[ff] response body NOT supported on this Firefox (documented): {exc}", flush=True)
        m.disconnect()
        check("disconnect clean (FF)", not m.connected)
    except Exception:
        print("[ff] ERROR:\n" + traceback.format_exc(), flush=True)
    finally:
        browser.close()
        print("[ff] browser+driver closed", flush=True)
    passed = sum(results)
    print(f"\n[ff] {passed}/{len(results)} checks passed", flush=True)
    return 0 if passed == len(results) and results else 1


if __name__ == "__main__":
    raise SystemExit(main())
