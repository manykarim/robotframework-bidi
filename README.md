# robotframework-bidi

A **WebDriver BiDi** engine for Robot Framework, with adapters for **both** the
[`Browser`](https://github.com/MarketSquare/robotframework-browser) library and
[`SeleniumLibrary`](https://github.com/robotframework/SeleniumLibrary).

```
bidi_core/      framework-neutral BiDi engine (websockets + chromium-bidi mapper)
Browser_BiDi/   Browser library adapter  (plugin)   ──┐
Selenium_BiDi/  SeleniumLibrary adapter (plugin)    ──┴─ thin, portable keywords
```

It opens an **independent BiDi connection** to the *same* browser the host
library is driving and exposes BiDi data and control — real network response
bodies, **request mocking / fault injection / auth**, raw console/JS-exception
streams, **emulation** (geo/locale/timezone/viewport), **isolated user
contexts**, input/uploads, navigation/downloads, and realm-scoped evaluation —
as Robot Framework keywords. Keyword names are kept parallel across the two
adapters so suites stay portable.

## Install

```bash
pip install robotframework-bidi[browser]     # Browser library adapter
pip install robotframework-bidi[selenium]    # SeleniumLibrary adapter
pip install robotframework-bidi              # core only (build your own adapter)
bidi-init                                    # check runtime (Chrome + bundled mapper)
```

The framework-neutral `bidi_core` depends only on `websockets`; host libraries
are optional extras. Chrome is **driverless** via the vendored chromium-bidi
mapper; Firefox is driverless via native BiDi — `bidi-init` reports status and
can refresh the mapper or fetch drivers (all opt-in).

## SeleniumLibrary quickstart

`Open BiDi Browser` opens a BiDi-enabled browser, registers it with
SeleniumLibrary (so `Go To`/`Close Browser`/… work), **and** connects BiDi — one
keyword, no helper library:

```robotframework
*** Settings ***
Library    SeleniumLibrary    plugins=${path}/Selenium_BiDi/SeleniumBiDi.py

*** Test Cases ***
Mock And Assert No Console Errors
    Open BiDi Browser     https://example.com/app    browser=chrome
    BiDi Subscribe        log.entryAdded, network.responseCompleted
    BiDi Mock Response    *://*/api/profile    body={"userId": 1}
    Get BiDi JS Error Count    ==    ${0}
    [Teardown]    Run Keywords    Disconnect BiDi    AND    Close All Browsers
```

`executable_path` is optional (empty uses Selenium Manager). To attach BiDi to a
browser you opened yourself (e.g. SeleniumLibrary's `Open Browser` with
`options.enable_bidi = True`), use `Connect BiDi` directly instead.

---

## Browser library adapter

The Browser adapter opens an **independent BiDi WebSocket** to the *same*
browser instance Playwright is already driving, exposing BiDi-only data — real
network response bodies, raw console/JS-exception streams, native event
subscriptions, and realm-scoped script evaluation — as Robot Framework keywords.

> **Why not "just use Playwright"?** The Browser library talks gRPC to a Node
> process running Playwright, which drives the browser over CDP. Playwright's own
> BiDi support is internal/experimental with **no public API**, and it is not
> surfaced across the gRPC bridge. So a true BiDi session cannot be obtained
> *through* the existing plumbing — this extension runs a **parallel** session
> instead. See [`docs/research/browser-bidi-extension-proposal.md`](docs/research/browser-bidi-extension-proposal.md).

## What it adds beyond Playwright/Browser

| Capability | BiDi side-channel adds |
|---|---|
| Network response **bodies** | First-class retrieval post-load |
| Network events | Continuous stream with timings, sizes, cache state |
| Console logs / JS errors | Raw `log.entryAdded` with level, args, stack, source, realm |
| Event subscription | Native `session.subscribe` for the whole run |
| Realm/sandbox evaluation | `script.evaluate` in arbitrary realms |
| Cross-browser uniformity | Standardised shape across Chrome/Edge/**Firefox** |

It is **observability-only** — it does not duplicate Playwright interaction
(clicks, locators, navigation). Use Browser keywords to *act*, Browser-BiDi
keywords to *observe*.

## Browser support (validated 2026-05-29 — see `spike/RESULTS.md`)

| Browser | Full Strategy-1 (Playwright + BiDi, same browser) | Response bodies | Network / console / errors / evaluate / correlation |
|---|---|---|---|
| **Chromium / Chrome / Edge** | ✅ via CDP (`Connect To Browser use_cdp=True`) | ✅ | ✅ |
| **Firefox** | ❌ not via Browser today¹ | ⚠️ unreliable² | ✅ (BiDi-client level) |
| **WebKit / Safari** | ❌ no BiDi | — | — |

¹ Firefox has no CDP, and Browser/Playwright cannot attach to an *externally*
launched Firefox — it launches its own — so the BiDi session and Playwright end
up on different Firefox instances. Firefox is supported at the **BiDi-client
level** (validated by `spike/run_firefox.py`), pending a way to point Playwright
at an external Firefox. ² Firefox `network.getData` fails on compressed streams;
response bodies are Chromium-reliable.

## Tested with

Chrome 147 + ChromeDriver 147 · Firefox 150 + geckodriver 0.36 ·
robotframework-browser 19.12 · robotframework 7.4 · websockets 16 · Python 3.12.

## Installation

```bash
pip install robotframework-browser-bidi
# plus the host library, if not already installed:
pip install robotframework-browser
rfbrowser init
```

## The launch contract (important)

The extension needs a browser that exposes **both**:

1. a **CDP** debugging endpoint, so Browser can `Connect To Browser ... use_cdp=True`; and
2. a reachable **BiDi** WebSocket, so this extension can `Connect BiDi`.

If the browser was not launched BiDi-reachable, `Connect BiDi` fails with an
actionable error.

### No WebDriver required — both browsers are driverless (validated)

Neither chromedriver nor geckodriver is needed:

| Browser | How a BiDi endpoint is obtained | Driver? |
|---|---|---|
| **Firefox** | Native BiDi: `firefox --remote-debugging-port=PORT --remote-allow-origins=*` → `ws://host:PORT/session`. `launch_firefox()` does this. | **None** |
| **Chrome/Chromium** | Chrome's port is CDP-only, so the bundled **chromium-bidi mapper** is loaded into a hidden tab over CDP (the same technique chromedriver uses, reimplemented in Python). `launch_chromium_driverless()` + `Connect BiDi … transport=cdp-mapper`. | **None** |

```robotframework
# Driverless Chrome (mapper): bidi_url is Chrome's CDP webSocketDebuggerUrl
Connect BiDi    ${WS_DEBUGGER_URL}    browser=chromium    transport=cdp-mapper
# Driverless Firefox (native): bidi_url is ws://host:port/session
Connect BiDi    ${FF_BIDI_URL}        browser=firefox
```

The chromium-bidi mapper bundle (Apache-2.0) is vendored at
`Browser_BiDi/mapper/mapperTab.js`; keep its version roughly aligned with your
Chrome. A chromedriver/geckodriver path is still available via
`launch_chromium(driverless=...)` / `launch_firefox(driverless=False)`. Empirically
(Chrome 147) the plain `/devtools/browser` socket returns
`{"error":{"code":-32601,"message":"'session.new' wasn't found"}}` for BiDi
methods — confirming the mapper is required. See `spike/RESULTS.md`.

**WebKit/Safari has no BiDi** and is rejected with a clear message.

## Usage

```robotframework
*** Settings ***
Library    Browser    plugins=${CURDIR}/BrowserBiDi.py

*** Test Cases ***
Capture Real Network Bodies
    Connect To Browser    http://localhost:9222    use_cdp=True
    Connect BiDi          ws://localhost:9222/session    browser=chromium
    BiDi Subscribe        network.responseCompleted, log.entryAdded
    New Page              https://example.com/app
    ${resp}=    Wait For BiDi Response    *://*/api/profile
    ${body}=    Get BiDi Response Body    ${resp}[request][request]
    Should Contain        ${body}    userId
    ${errors}=  Get BiDi JS Errors
    Should Be Empty       ${errors}
    [Teardown]    Run Keywords    Disconnect BiDi    AND    Close Browser
```

## Self-launching (no driver, no helper script)

The extension can launch its own BiDi-reachable browser as a keyword — driverless
by default (Chrome via the bundled mapper, Firefox native). The launched browser
is tracked and torn down automatically on `Close BiDi Browser`, `Disconnect BiDi`,
or process exit.

```robotframework
*** Settings ***
Library    Browser    plugins=${CURDIR}/BrowserBiDi.py

*** Test Cases ***
Self-Launching BiDi
    ${b}=    Launch BiDi Browser    chromium          # {bidi_url, cdp_url, transport, browser}
    Connect To Browser    ${b}[cdp_url]    use_cdp=True
    Connect BiDi          ${b}[bidi_url]   transport=${b}[transport]
    New Page              about:blank
    Go To                 https://example.com/
    Wait For BiDi Response      *example.com*
    Get BiDi Response Status    *example.com*    ==    ${200}
    [Teardown]    Run Keywords    Close Browser    AND    Disconnect BiDi
```

## Keywords

**Launch:** `Launch BiDi Browser`, `Close BiDi Browser`
**Session:** `Connect BiDi`, `Disconnect BiDi`, `BiDi Subscribe`,
`BiDi Unsubscribe`, `Clear BiDi Buffers`, `Get BiDi Context For Current Page`,
`Get BiDi Contexts`
**Network:** `Get BiDi Network Events`, `Get BiDi Response Body`*,
`Get BiDi Response Status`*, `Get BiDi Response Headers`*,
`Get BiDi Network Event Count`*, `Get BiDi Resource Timings`*,
`Get BiDi Slowest Resources`*, `Get BiDi Largest Resources`*,
`Get BiDi Response Timing`*, `Wait For BiDi Response`
**Logs:** `Get BiDi Console Log`*, `Get BiDi Console Log Count`*,
`Get BiDi JS Errors`*, `Get BiDi JS Error Count`*, `Wait For BiDi Log Entry`
**Page/DOM/A11y:** `Get BiDi Url`*, `Get BiDi Title`*, `Get BiDi DOM Snapshot`*,
`Get BiDi Aria Snapshot`*, `Get BiDi Elements`*, `Get BiDi Element Count`*,
`Get BiDi Element Text`*, `Take BiDi Screenshot`
**Storage:** `Get BiDi Cookies`*
**Performance:** `Get BiDi Web Vitals`*
**Script:** `BiDi Evaluate`*, `BiDi Add Preload Script`
**Diagnostics:** `Log BiDi Diagnostics`

`*` = **Getter/Assertion** keyword following the Browser library pattern
(powered by `robotframework-assertionengine`): it returns the value *and*
optionally asserts in one call. All keywords return plain JSON-serialisable
Python (dicts/lists).

### Getter + assertion in one call

```robotframework
Get BiDi Response Status    *://*/api/profile    ==           ${200}
Get BiDi Title                                   ==           My App
Get BiDi JS Error Count                          ==           ${0}
Get BiDi Element Count      css    .todo-item     greater than ${0}
Get BiDi Response Headers   *://*/api/*           contains     content-type
${vitals}=    Get BiDi Web Vitals
```

### Performance analysis, console search, ARIA snapshot

Top-N network/performance analysis — flexible (`top`/`phase`/`url_glob`) yet
readable; each entry has timing phases + `size`/`status`/`mime`:

```robotframework
${slowest}=    Get BiDi Slowest Resources    top=10                 # by total load time
${ttfb}=       Get BiDi Slowest Resources    top=10    phase=ttfb
${biggest}=    Get BiDi Largest Resources    top=10                 # by transferred bytes
Get BiDi Resource Timings    sort_by=size    top=5    url_glob=*/static/*
```

Search/filter console output by substring or regex:

```robotframework
${orders}=    Get BiDi Console Log    text=checkout
${codes}=     Get BiDi Console Log    pattern=E_[A-Z]+    level=error
```

ARIA snapshot (role + accessible name tree), cross-engine via BiDi — also
available in the **SeleniumLibrary** adapter:

```robotframework
Get BiDi Aria Snapshot    contains    - heading "Checkout"
Get BiDi Aria Snapshot    contains    - button "Pay now"    selector=#cart
```

### Shadow DOM and iframes

Locators do **not** cross shadow boundaries (standard selector semantics). Use
`pierce_shadow=True` (css only) to read **open shadow DOM**:

```robotframework
Get BiDi Element Count    css    .inside-shadow    pierce_shadow=True    ==    ${1}
Get BiDi Element Text     css    .inside-shadow    pierce_shadow=True
```

**Iframes** are separate browsing contexts — pass their `context` id (from the
context tree) to target inside a frame.

### Capture BiDi state on failure

Point Browser's run-on-failure at the diagnostics keyword to automatically log
recent JS errors and dropped-event counts when a test fails:

```robotframework
Library    Browser    plugins=${CURDIR}/BrowserBiDi.py    run_on_failure=Log BiDi Diagnostics
```

## Architecture

```
Browser (Python) ──gRPC──▶ Node/Playwright ──CDP──▶ Browser process
      │                                                   ▲
      │ plugins=BrowserBiDi.py                            │ BiDi WebSocket
      ▼                                                   │ (independent)
BrowserBiDi (LibraryComponent)  ───────────────────────────┘
  • dedicated asyncio loop on a background thread
  • thin swappable BiDi client (websockets JSON-RPC duplex)
  • bounded per-event-class buffers
  • page ↔ context correlation via a tiny bundled jsextension
```

See [`openspec/changes/browser-bidi-extension/design.md`](openspec/changes/browser-bidi-extension/design.md)
for the design decisions and trade-offs.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
pytest                       # unit tests (no browser required)
pytest tests/integration     # integration tests (require live browsers + drivers)
```

The thin BiDi client, buffers, and correlation logic are unit-tested with a fake
transport and require no browser. Integration tests and the Phase 0 spike
(`spike/bidi_spike.py`) require a BiDi-reachable browser.

## License

Apache-2.0.
