#!/usr/bin/env python3
# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Live validation of the getter/assertion data layer against real Chromium.

Exercises the production BiDiManager methods behind the Getter/Assertion
keywords: response status/headers, network event count, resource timings, url,
title, DOM snapshot, element count/text, web vitals, cookies, screenshot,
accessibility locator, shadow-DOM piercing, and iframe (separate context).
Requires chromedriver on PATH. Run: ``python spike/run_getters.py``"""
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from Browser_BiDi.launcher import launch_chromium
from Browser_BiDi.manager import BiDiManager

SHADOW_URL = (ROOT / "spike" / "shadow.html").as_uri()
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" :: {detail}" if detail else ""), flush=True)


def navigate(m, ctx, url):
    m._loop.run(m._client.send_command(
        "browsingContext.navigate", {"context": ctx, "url": url, "wait": "complete"}), timeout=30)


def main():
    b = launch_chromium(port=9598, headless=True, extra_args=["--no-sandbox", "--disable-dev-shm-usage"])
    m = BiDiManager(buffer_size=300)
    try:
        m.connect(b.bidi_url, browser="chromium",
                  auto_subscribe=["network.responseCompleted", "log.entryAdded"])
        ctx = m._loop.run(m._commands.browsing_context.get_tree(), timeout=10)["contexts"][0]["context"]

        navigate(m, ctx, "https://example.com/"); time.sleep(1)
        check("response status == 200", m.get_response_status("*example.com*") == 200)
        check("response headers has content-type", "content-type" in m.get_response_headers("*example.com*"))
        check("network event count >= 1", m.get_network_event_count() >= 1)
        rt = m.get_resource_timings(url_glob="*example.com*")
        check("resource timings has total", rt and rt[0].get("total") is not None)
        check("url", "example.com" in m.get_url())
        check("title == Example Domain", m.get_title() == "Example Domain")
        check("dom snapshot has <html", "<html" in m.get_dom_snapshot().lower())
        check("element count css h1 == 1", m.get_element_count("css", "h1") == 1)
        check("element text css h1", m.get_element_text("css", "h1") == "Example Domain")
        check("web vitals has fcp", m.get_web_vitals().get("fcp") is not None)
        check("cookies returns list", isinstance(m.get_cookies(), list))
        check("screenshot non-empty", len(m.capture_screenshot()) > 100)
        check("accessibility locator role=heading", m.get_element_count("accessibility", "role=heading") >= 1)

        navigate(m, ctx, SHADOW_URL); time.sleep(0.5)
        check("light DOM h1 == 1", m.get_element_count("css", "h1") == 1)
        check("locateNodes does NOT cross shadow (0)", m.get_element_count("css", ".shadow-btn") == 0)
        check("shadow pierce count == 1", m.get_element_count("css", ".shadow-btn", pierce_shadow=True) == 1)
        check("shadow pierce text", m.get_element_text("css", ".shadow-btn", pierce_shadow=True) == "Shadow Button")
        check("iframe isolation (top sees 0)", m.get_element_count("css", ".in-frame") == 0)
        kids = m._loop.run(m._commands.browsing_context.get_tree(), timeout=10)["contexts"][0].get("children") or []
        check("iframe child context .in-frame == 1",
              bool(kids) and m.get_element_count("css", ".in-frame", context=kids[0]["context"]) == 1)
        m.disconnect()
    except Exception:
        print("ERROR:\n" + traceback.format_exc(), flush=True)
    finally:
        b.close()
    print(f"\n{sum(results)}/{len(results)} checks passed", flush=True)
    return 0 if results and sum(results) == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
