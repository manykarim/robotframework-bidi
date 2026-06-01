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
"""Launch helper for a BiDi-reachable browser (design.md; tasks 8.1/8.2).

Starts a browser that exposes BOTH a CDP debugging endpoint (so the Browser
library can ``Connect To Browser ... use_cdp=True``) AND a reachable BiDi
WebSocket (so this extension can ``Connect BiDi``). This is the launch contract
the whole extension depends on (proposal risk #1).

Strategies (design.md D2):
  * Chromium  -> chromedriver exposes a BiDi ``webSocketUrl`` and proxies CDP.
  * Firefox   -> geckodriver exposes a BiDi ``webSocketUrl``.

The drivers are required on PATH. This module shells out to them and parses the
returned ``webSocketUrl`` capability; it intentionally avoids adding a Selenium
dependency.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class LaunchedBrowser:
    """Endpoints for a launched, BiDi-reachable browser."""

    browser: str
    bidi_url: str
    cdp_url: Optional[str]
    driver_process: subprocess.Popen
    session_id: str
    driver_url: str = ""
    pgid: Optional[int] = None  # set for driverless launches (kill the whole tree)

    def close(self) -> None:
        # Delete the WebDriver session first so the driver quits the browser
        # cleanly. geckodriver in particular does NOT kill its Firefox child
        # when merely terminated, which orphans the browser (found in testing).
        if self.driver_url and self.session_id:
            try:
                request = urllib.request.Request(
                    f"{self.driver_url}/session/{self.session_id}", method="DELETE"
                )
                urllib.request.urlopen(request, timeout=10).close()
            except Exception:  # noqa: BLE001 - fall through to terminating the driver
                pass
        if self.pgid is not None:
            # Driverless: the browser is its own process tree; kill the group.
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(self.pgid, sig)
                except ProcessLookupError:
                    return
                try:
                    self.driver_process.wait(timeout=5)
                    return
                except subprocess.TimeoutExpired:
                    continue
            return
        if self.driver_process.poll() is None:
            self.driver_process.terminate()
            try:
                self.driver_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.driver_process.kill()


def _wait_until_ready(driver_url: str, *, timeout: float = 20.0) -> None:
    """Poll the driver's ``/status`` endpoint until it is listening and ready.

    The driver binds its port asynchronously after launch, so POSTing /session
    immediately races and is refused (found via the Phase 0 spike).
    """
    deadline = time.monotonic() + timeout
    last_error: Optional[Exception] = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{driver_url}/status", timeout=2) as response:
                body = json.loads(response.read())
                if body.get("value", {}).get("ready", True):
                    return
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"driver at {driver_url} not ready within {timeout}s: {last_error}")


def _new_session(driver_url: str, capabilities: dict) -> dict:
    request = urllib.request.Request(
        f"{driver_url}/session",
        data=json.dumps({"capabilities": capabilities}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())["value"]


def launch_chromium(
    *,
    port: int = 9515,
    headless: bool = True,
    binary: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
) -> LaunchedBrowser:
    """Launch Chrome/Chromium via chromedriver with BiDi enabled.

    ``extra_args`` are appended to the browser command line (e.g.
    ``--no-sandbox`` in a container).
    """
    args = ["--headless=new"] if headless else []
    args += list(extra_args or [])
    return _launch(
        driver="chromedriver",
        driver_args=[f"--port={port}"],
        port=port,
        browser_name="chromium",
        options_key="goog:chromeOptions",
        args=args,
        binary=binary,
    )


def launch_chromium_driverless(
    *,
    port: int = 0,
    headless: bool = True,
    binary: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
) -> LaunchedBrowser:
    """Launch Chrome with CDP only (NO chromedriver) for driverless BiDi.

    Returns ``bidi_url`` = Chrome's CDP ``webSocketDebuggerUrl``; connect with
    ``transport="cdp-mapper"`` so BiDi is spoken through the chromium-bidi mapper.
    Also exposes ``cdp_url`` for Playwright ``Connect To Browser use_cdp=True``.
    """
    profile = tempfile.mkdtemp(prefix="bidi-cr-")
    cmd = [binary or "google-chrome"]
    if headless:
        cmd.append("--headless=new")
    cmd += [
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        *(extra_args or []),
    ]
    log = tempfile.NamedTemporaryFile(prefix="bidi-cr-", suffix=".log", delete=False)
    process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    # Chrome prints "DevTools listening on ws://..." once the port is bound.
    deadline = time.monotonic() + 30
    ws_browser = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Chrome exited before exposing a debugging endpoint.")
        match = re.search(r"DevTools listening on (ws://\S+)", Path(log.name).read_text(errors="ignore"))
        if match:
            ws_browser = match.group(1)
            break
        time.sleep(0.2)
    if not ws_browser:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        raise RuntimeError("Chrome did not expose a DevTools endpoint within 30s.")
    # Derive the HTTP base for Playwright connectOverCDP from the ws URL.
    host_port = ws_browser.split("/devtools/")[0].replace("ws://", "")
    return LaunchedBrowser(
        browser="chromium",
        bidi_url=ws_browser,  # speak BiDi over this via transport="cdp-mapper"
        cdp_url=f"http://{host_port}",
        driver_process=process,
        session_id="",
        driver_url="",
        pgid=os.getpgid(process.pid),
    )


def launch_firefox(
    *,
    port: int = 9233,
    headless: bool = True,
    binary: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    driverless: bool = True,
) -> LaunchedBrowser:
    """Launch Firefox with WebDriver BiDi reachable.

    By default this is **driverless** (no geckodriver): Firefox exposes a native
    BiDi endpoint via ``--remote-debugging-port`` (validated — see
    spike/RESULTS.md). Set ``driverless=False`` to use geckodriver instead.
    """
    if not driverless:
        args = ["-headless"] if headless else []
        args += list(extra_args or [])
        return _launch(
            driver="geckodriver",
            driver_args=[f"--port={port}"],
            port=port,
            browser_name="firefox",
            options_key="moz:firefoxOptions",
            args=args,
            binary=binary,
        )
    return _launch_firefox_driverless(port, headless, binary, extra_args)


def _launch_firefox_driverless(
    port: int, headless: bool, binary: Optional[str], extra_args: Optional[List[str]]
) -> LaunchedBrowser:
    profile = tempfile.mkdtemp(prefix="bidi-ff-")
    cmd = [binary or "firefox"]
    if headless:
        cmd.append("--headless")
    cmd += [
        f"--remote-debugging-port={port}",
        "--remote-allow-hosts=localhost",
        "--remote-allow-origins=*",
        "-profile", profile, "-no-remote",
        *(extra_args or []),
    ]
    log = tempfile.NamedTemporaryFile(prefix="bidi-ff-", suffix=".log", delete=False)
    # Own process group so close() can kill Firefox and all its children.
    process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.monotonic() + 30
    base: Optional[str] = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Firefox exited before announcing a BiDi endpoint.")
        text = Path(log.name).read_text(errors="ignore")
        match = re.search(r"WebDriver BiDi listening on (ws://\S+)", text)
        if match:
            base = match.group(1)
            break
        time.sleep(0.2)
    if not base:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        raise RuntimeError("Firefox did not announce a BiDi endpoint within 30s.")
    return LaunchedBrowser(
        browser="firefox",
        bidi_url=base.rstrip("/") + "/session",
        cdp_url=None,
        driver_process=process,
        session_id="",
        driver_url="",
        pgid=os.getpgid(process.pid),
    )


def _launch(
    *,
    driver: str,
    driver_args: List[str],
    port: int,
    browser_name: str,
    options_key: str,
    args: List[str],
    binary: Optional[str],
) -> LaunchedBrowser:
    process = subprocess.Popen([driver, *driver_args])  # noqa: S603 - trusted driver name
    driver_url = f"http://127.0.0.1:{port}"
    # webSocketUrl:true asks the driver to return a BiDi endpoint in the
    # session capabilities.
    options: dict = {"args": args}
    if binary:
        options["binary"] = binary
    capabilities = {
        "alwaysMatch": {
            "browserName": browser_name if browser_name != "chromium" else "chrome",
            "webSocketUrl": True,
            options_key: options,
        }
    }
    try:
        _wait_until_ready(driver_url)
        value = _new_session(driver_url, capabilities)
    except Exception:
        # Never leak the driver subprocess if startup/handshake fails.
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        raise
    bidi_url = value.get("capabilities", {}).get("webSocketUrl")
    if not bidi_url:
        process.terminate()
        raise RuntimeError(
            f"{driver} did not return a BiDi webSocketUrl; ensure a recent driver/browser."
        )
    cdp_url = value.get("capabilities", {}).get("goog:chromeOptions", {}).get(
        "debuggerAddress"
    )
    if cdp_url:
        # Use 127.0.0.1, not 'localhost': Chrome listens on IPv4 only, but
        # 'localhost' can resolve to IPv6 (::1) and Playwright's connectOverCDP
        # then fails with ECONNREFUSED ::1.
        cdp_url = "http://" + cdp_url.replace("localhost", "127.0.0.1")
    return LaunchedBrowser(
        browser=browser_name,
        bidi_url=bidi_url,
        cdp_url=cdp_url,
        driver_process=process,
        session_id=value.get("sessionId", ""),
        driver_url=driver_url,
    )
