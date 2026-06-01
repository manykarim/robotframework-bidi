# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Robot library for the example suites.

Self-contained: launches a DRIVERLESS Chrome (CDP for Playwright + BiDi via the
chromium-bidi mapper) and serves the `pages/` fixtures over HTTP, publishing
``${CDP_URL}``, ``${BIDI_URL}``, ``${BIDI_TRANSPORT}`` and ``${BASE_URL}`` as
suite variables. Requires `google-chrome` on PATH; skips gracefully otherwise.
"""

import functools
import http.server
import json
import threading
from pathlib import Path
from urllib.parse import urlparse

from robot.api import logger
from robot.api.deco import keyword, library
from robot.libraries.BuiltIn import BuiltIn

from Browser_BiDi.launcher import launch_chromium_driverless

PAGES_DIR = Path(__file__).parent / "pages"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serves pages/ plus a few dynamic routes for the BiDi examples:
    ``/auth`` (HTTP Basic), ``/echo-headers`` (JSON of request headers),
    ``/download`` (attachment)."""

    protocol_version = "HTTP/1.1"  # allow keep-alive; threaded server below

    def log_message(self, *args):  # silence per-request stderr logging
        pass

    def _send(self, code, body=b"", content_type="text/plain", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/auth":
            if (self.headers.get("Authorization") or "").startswith("Basic "):
                self._send(200, b'{"authed": true}', "application/json")
            else:
                self._send(401, b"", extra={"WWW-Authenticate": 'Basic realm="demo"'})
            return
        if path == "/echo-headers":
            hdrs = {k.lower(): v for k, v in self.headers.items()}
            self._send(200, json.dumps({"headers": hdrs}).encode(), "application/json")
            return
        if path.startswith("/download"):
            self._send(200, b"demo download contents", "application/octet-stream",
                       extra={"Content-Disposition": 'attachment; filename="report.txt"'})
            return
        super().do_GET()


@library(scope="SUITE")
class BiDiBrowserLauncher:
    def __init__(self) -> None:
        self._browser = None
        self._httpd = None

    @keyword
    def start_bidi_browser(self) -> None:
        try:
            self._browser = launch_chromium_driverless(
                headless=True, extra_args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
        except FileNotFoundError:
            BuiltIn().skip("google-chrome not found on PATH; skipping live BiDi example.")
        except Exception as exc:  # noqa: BLE001
            BuiltIn().skip(f"Could not launch a BiDi+CDP browser: {exc}")

        handler = functools.partial(_QuietHandler, directory=str(PAGES_DIR))
        # Threaded so a page with an iframe + several resources doesn't block on
        # a single-threaded server (caused page.goto timeouts under load).
        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._httpd.daemon_threads = True
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        base_url = f"http://127.0.0.1:{self._httpd.server_address[1]}/"

        logger.info(f"driverless browser cdp={self._browser.cdp_url} bidi={self._browser.bidi_url}")
        logger.info(f"serving fixtures at {base_url}")
        BuiltIn().set_suite_variable("${CDP_URL}", self._browser.cdp_url)
        BuiltIn().set_suite_variable("${BIDI_URL}", self._browser.bidi_url)
        BuiltIn().set_suite_variable("${BIDI_TRANSPORT}", "cdp-mapper")
        BuiltIn().set_suite_variable("${BASE_URL}", base_url)

    @keyword
    def stop_bidi_browser(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None
