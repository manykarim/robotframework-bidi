# Browser-BiDi examples

Realistic, self-contained Robot Framework suites covering **all** Browser-BiDi
keywords. Each suite launches a **driverless** Chrome (no chromedriver — CDP for
Playwright + BiDi via the chromium-bidi mapper) and serves the `pages/` fixtures
over a local HTTP server, so cookies, fetch/XHR, console output, JS errors,
shadow DOM and iframes are all exercised against real pages.

## Running

```bash
# from the repo root, with google-chrome on PATH
pip install -e .            # installs the plugin + Browser
rfbrowser init              # one-time, sets up the Browser library's Node side
PYTHONPATH=. robot -d results examples/
```

Suites skip gracefully if `google-chrome` is not found.

## Suites

| Suite | Scenarios | Keywords covered |
|---|---|---|
| `bidi_example.robot` | Quickstart: body capture, no-JS-errors, getter+assert | Connect/Disconnect, Subscribe, Wait For BiDi Response, Get BiDi Response Body/Status, Get BiDi Title/Element Count, Get BiDi JS Error Count |
| `network_traffic.robot` | Inspect an API response; list/count requests; per-resource timings; **top-N slowest/largest**; (un)subscribe | Get BiDi Network Events/Event Count, Response Status/Headers/Body, Resource Timings, Slowest/Largest Resources, Response Timing, Wait For BiDi Response, BiDi (Un)Subscribe |
| `console_and_errors.robot` | Capture console; filter by level; **search by text/regex**; detect uncaught errors; diagnostics | Get BiDi Console Log/Count, JS Errors/Count, Wait For BiDi Log Entry, Log BiDi Diagnostics |
| `dom_inspection.robot` | Page identity; locate elements; accessibility role; **open shadow DOM**; **iframe** content; DOM snapshot; **ARIA snapshot** | Get BiDi Url/Title/DOM Snapshot, Aria Snapshot, Elements/Element Count/Element Text, Context For Current Page, Contexts |
| `storage_and_performance.robot` | Read cookies; Web Vitals timing; screenshots | Get BiDi Cookies, Web Vitals, Take BiDi Screenshot |
| `script_evaluation.robot` | Evaluate expressions; structured returns; preload script | BiDi Evaluate, BiDi Add Preload Script |
| `network_interception.robot` | Mock/fault/auth/headers/cache; clear; per-request timing | BiDi Mock Response, Fail Request, Inject Headers, Provide Auth, Set Cache Behavior, Clear Intercepts, Get BiDi Response Timing |
| `emulation.robot` | Locale/timezone/user-agent/geolocation/viewport; gating; matrix | BiDi Set Locale/Timezone/User Agent/Geolocation/Viewport/Forced Colors/Scripting Enabled, Get BiDi Support Matrix |
| `isolation.robot` | Hermetic user-context isolation | New/Remove BiDi User Context, New BiDi Context In User Context |
| `input_and_storage.robot` | File upload, wheel/raw actions, cookie write/delete | BiDi Set Files, Perform Actions, Wheel Scroll, Set Cookie, Delete Cookies |
| `navigation_and_downloads.robot` | Navigation lifecycle + SPA route; managed download | Wait For BiDi Navigation, Get BiDi Navigation Events, Set Download Behavior, Wait For BiDi Download |
| `self_launching.robot` | Extension launches its own browser (driverless) | Launch BiDi Browser, Close BiDi Browser |
| `selenium/selenium_bidi_example.robot` | The SeleniumLibrary adapter — **every** Selenium-BiDi keyword | Open BiDi Browser + the full Selenium keyword set |

**Every Browser-adapter keyword (63) and every Selenium-adapter keyword (29) is
exercised by at least one example.** `Clear BiDi Buffers` is used in the shared
`Test Setup` (`bidi_setup.resource`) for clean per-test counts. All getter
keywords (`Get BiDi …`) follow the Browser library pattern: they return the value
and optionally assert in one call (`==`, `contains`, `greater than`, …).
Capability-gated keywords (e.g. forced-colors on Chromium) fail fast with a clear
message — see `emulation.robot`.

## Fixtures (`pages/`)

`index.html` (cookie + fetch + console), `app.html` (form, todo list, a custom
element with **open shadow DOM**, an **iframe**, console.warn), `errors.html`
(uncaught exceptions), `frame.html`, plus `style.css` / `app.js` / `pixel.png` /
`api/data.json` so network/timing examples see multiple resources.

## Notes

- Driverless Chrome uses the vendored chromium-bidi mapper; the suites warm up a
  tracked page in `Suite Setup` so the *first* navigation's network events are
  captured reliably.
- Firefox is also driverless (`launch_firefox()`), but full Strategy-1
  coexistence (Playwright + BiDi on the same browser) is Chromium-only — see the
  repo README.
