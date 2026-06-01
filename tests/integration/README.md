# Integration tests (require live browsers)

These suites exercise the plugin against a **real** BiDi-reachable browser and
validate per-browser correlation (task 6.6). They are **not** run by the default
`pytest` invocation (`pyproject.toml` ignores `tests/integration`).

## Prerequisites

- `robotframework-browser` installed (`rfbrowser init` run).
- `chromedriver` (for Chromium) and/or `geckodriver` (for Firefox) on `PATH`.
- A browser launched with both a CDP endpoint and a reachable BiDi WebSocket.
  Use `Browser_BiDi.launcher.launch_chromium()` / `launch_firefox()`.

## Run

```bash
# Chromium
robot --variable BIDI_URL:ws://localhost:9222/session \
      --variable CDP_URL:http://localhost:9222 \
      tests/integration/test_chromium.robot

# Firefox (use the geckodriver webSocketUrl as BIDI_URL)
robot --variable BIDI_URL:ws://... tests/integration/test_firefox.robot
```

Correlation (page ↔ BiDi context) is the main fragility surface; these suites
assert it per browser. If they fail at `Connect BiDi`, the browser was not
launched BiDi-reachable.
