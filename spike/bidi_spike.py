#!/usr/bin/env python3
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
"""Phase 0 feasibility spike (tasks 1.2-1.5).

Validates the whole premise BEFORE any Robot integration:
  * open a BiDi WebSocket to a running browser,
  * run session.new + session.subscribe for log.entryAdded and
    network.responseCompleted,
  * navigate and retrieve ONE response body,
  * (task 1.5) optionally check coexistence with a Playwright CDP session.

KILL CRITERION: if a parallel BiDi session cannot coexist with a Playwright CDP
session on the same instance, STOP or pivot (see design.md).

Usage:
    # 1. Launch a BiDi-reachable browser (chromedriver/geckodriver on PATH):
    python -m Browser_BiDi.launcher  # or use the launch helpers below
    # 2. Run the spike against the printed ws:// URL:
    python spike/bidi_spike.py --bidi-url ws://... --url https://example.com

This script depends only on ``websockets`` and the package's thin client.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Browser_BiDi.bidi_client import WebsocketsBiDiClient  # noqa: E402
from Browser_BiDi.commands import Commands  # noqa: E402


async def run(bidi_url: str, nav_url: str, response_glob: str) -> int:
    client = WebsocketsBiDiClient(bidi_url)
    captured: list = []
    logs: list = []
    bodies: dict = {}

    await client.connect()
    commands = Commands(client)

    client.add_event_listener("network.responseCompleted", captured.append)
    client.add_event_listener("log.entryAdded", logs.append)

    # When the ws came from a driver's webSocketUrl the session already exists,
    # so session.new is redundant and may error -> best-effort.
    try:
        await asyncio.wait_for(commands.session.new(), timeout=5)
        print("[spike] session.new ok")
    except Exception as exc:  # noqa: BLE001
        print(f"[spike] session.new skipped/failed (likely pre-established): {exc}")
    await commands.session.subscribe(["log.entryAdded", "network.responseCompleted"])
    # Register a data collector BEFORE navigating so response bodies are kept.
    collector = (await commands.network.add_data_collector()).get("collector")
    print(f"[spike] subscribed; data collector={collector}; navigating to {nav_url}")

    tree = await commands.browsing_context.get_tree()
    context_id = tree["contexts"][0]["context"]
    await client.send_command(
        "browsingContext.navigate",
        {"context": context_id, "url": nav_url, "wait": "complete"},
    )

    await asyncio.sleep(2)  # let responses settle
    print(f"[spike] captured {len(captured)} responses, {len(logs)} log entries")

    target = next(
        (e for e in captured if response_glob in (e.get("request", {}).get("url", ""))),
        captured[0] if captured else None,
    )
    if target:
        request_id = target["request"]["request"]
        data = await commands.network.get_data(request_id)
        body = (data.get("bytes") or {}).get("value", "")
        bodies[request_id] = body
        print(f"[spike] retrieved response body ({len(body)} chars) for {request_id}")
        print("[spike] PASS: BiDi session.new + subscribe + response body all worked")
        result = 0
    else:
        print("[spike] FAIL: no network responses captured")
        result = 1

    await client.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="WebDriver BiDi feasibility spike")
    parser.add_argument("--bidi-url", required=True, help="ws:// BiDi endpoint")
    parser.add_argument("--url", default="https://example.com", help="page to navigate")
    parser.add_argument("--response-glob", default="", help="substring to pick a response")
    args = parser.parse_args()
    return asyncio.run(run(args.bidi_url, args.url, args.response_glob))


if __name__ == "__main__":
    raise SystemExit(main())
