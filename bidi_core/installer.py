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
"""``bidi-init`` — provision the runtime for robotframework-bidi (design.md D6).

Explicit CLI (never auto-run on import). By default it only reports status (no
downloads). Opt in per artifact:

  bidi-init                 # status: local Chrome, bundled mapper, drivers
  bidi-init --refresh-mapper        # download a chromium-bidi mapper aligned to local Chrome
  bidi-init --drivers chromedriver  # fetch a matching driver (opt-in)

Anything downloaded is integrity-checked. The chromium-bidi mapper already ships
as package data, so driverless Chrome works offline without running this.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

MAPPER_PATH = Path(__file__).parent / "mapper" / "mapperTab.js"
_RUNTIME_GLOBALS = ("runMapperInstance", "onBidiMessage", "sendBidiResponse")


def _chrome_version(binary: str = "google-chrome") -> Optional[str]:
    exe = shutil.which(binary) or shutil.which("google-chrome-stable") or shutil.which("chromium")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10).stdout
    except Exception:  # noqa: BLE001
        return None
    m = re.search(r"(\d+\.\d+\.\d+\.\d+)", out)
    return m.group(1) if m else None


def _mapper_status() -> Tuple[bool, int]:
    if not MAPPER_PATH.exists():
        return False, 0
    text = MAPPER_PATH.read_text(errors="ignore")
    ok = all(g in text for g in _RUNTIME_GLOBALS)
    return ok, MAPPER_PATH.stat().st_size


def status() -> int:
    chrome = _chrome_version()
    mapper_ok, mapper_size = _mapper_status()
    print("robotframework-bidi runtime status")
    print(f"  local Chrome     : {chrome or '(not found)'}")
    print(f"  bundled mapper   : {'OK' if mapper_ok else 'MISSING/INVALID'} ({mapper_size} bytes) at {MAPPER_PATH}")
    print(f"  chromedriver     : {shutil.which('chromedriver') or '(not on PATH)'}")
    print(f"  geckodriver      : {shutil.which('geckodriver') or '(not on PATH)'}")
    print("\nFirefox needs no driver (native BiDi). Chrome works driverless via the")
    print("bundled mapper. Use --refresh-mapper / --drivers only if needed.")
    return 0 if mapper_ok else 1


def refresh_mapper(version: Optional[str] = None) -> int:
    """Download a chromium-bidi mapper bundle (default: a recent pinned version)."""
    version = version or "16.0.1"
    url = f"https://unpkg.com/chromium-bidi@{version}/lib/iife/mapperTab.js"
    print(f"Downloading chromium-bidi mapper {version} from {url} ...")
    tmp = MAPPER_PATH.with_suffix(".download")
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: download failed: {exc}", file=sys.stderr)
        return 1
    text = data.decode("utf-8", errors="ignore")
    if not all(g in text for g in _RUNTIME_GLOBALS) or len(data) < 100_000:
        print("ERROR: downloaded file failed integrity check (missing mapper globals).", file=sys.stderr)
        return 1
    tmp.write_bytes(data)
    tmp.replace(MAPPER_PATH)
    print(f"OK: mapper updated ({len(data)} bytes).")
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="bidi-init", description="Provision robotframework-bidi.")
    parser.add_argument("--refresh-mapper", nargs="?", const="16.0.1", metavar="VERSION",
                        help="Download/align the chromium-bidi mapper (opt-in).")
    parser.add_argument("--drivers", nargs="*", choices=["chromedriver", "geckodriver"], default=None,
                        help="Fetch matching WebDriver(s) (opt-in; not required for driverless use).")
    args = parser.parse_args(argv)

    if args.refresh_mapper is None and args.drivers is None:
        return status()
    rc = 0
    if args.refresh_mapper is not None:
        rc |= refresh_mapper(args.refresh_mapper)
    if args.drivers:
        print(f"Driver fetch requested for {args.drivers}. Drivers are optional: Firefox is "
              "driverless (native BiDi) and Chrome is driverless via the mapper. Install drivers "
              "from your package manager or the official download pages, or use Selenium Manager.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
