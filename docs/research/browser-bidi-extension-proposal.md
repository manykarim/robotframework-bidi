# Solution Proposal: A WebDriver BiDi Extension for Robot Framework Browser

**Goal:** Evaluate whether and how to build an extension for the Robot Framework `Browser`
library that connects to a browser instance over the **WebDriver BiDi** protocol and exposes
additional data *beyond* what Playwright surfaces, and propose a concrete, buildable solution.

**Status:** Architecture & feasibility analysis + recommended design. Not yet implemented.

**Author context:** Drafted for the `robotframework-browser-extensions` mono-repo
(MarketSquare), consistent with its existing extension pattern.

---

## 1. Executive summary

The short version:

- The `Browser` library is **not** a thin Python wrapper around Playwright. It is a Python
  Robot Framework library that talks **gRPC** to a long-lived **Node.js** process, which in
  turn drives the **Playwright (JS)** library. Every keyword is a gRPC round-trip.
- Playwright's transport to the actual browser is **CDP** (Chromium) or its own patched
  protocols (Firefox/WebKit). Playwright's own **WebDriver BiDi support is experimental and
  internal** — it is exercised only by Playwright's own test harness (`tests/bidi`), is gated
  behind unstable channel names, and exposes **no public, stable API** to "give me a BiDi
  session for this page". You cannot reach into Browser → Node → Playwright and pull out a
  usable BiDi connection.
- **Therefore a "true BiDi" extension routed *through* the Browser/Playwright plumbing is not
  feasible today.** What *is* feasible — and is the recommended design — is a **side-channel
  BiDi session**: the extension opens its **own** WebSocket BiDi connection to the *same*
  running browser instance that Browser/Playwright is already driving, correlates it to the
  Playwright session via the browser's debugging endpoint, and exposes BiDi-only data as new
  Robot Framework keywords.
- This gives genuine added value: **network response bodies, raw console/JS-exception events,
  real-time event subscriptions, cross-browser log capture, and `script` realm evaluation** —
  data that Playwright either does not expose at all or only exposes through lossy wrappers.
- The cleanest packaging is a **Browser library Plugin** (Python class inheriting
  `LibraryComponent`), shipped as `Browser-BiDi` in the extensions repo, with an optional
  thin Python BiDi client (or reuse of an existing one). A pure-JS `jsextension` is **not**
  suitable because the BiDi work is connection/event-loop heavy and belongs in Python.

The rest of this document justifies each of these claims and specifies the design.

---

## 2. How Browser library extensibility actually works

The Browser library documents **three** official extension mechanisms. Understanding their
boundaries is essential to picking the right one.

### 2.1 The runtime architecture (why this matters)

```
┌─────────────────────┐     gRPC      ┌──────────────────────┐   CDP / patched proto   ┌──────────┐
│ Robot Framework      │  (localhost) │ Node.js process       │ ─────────────────────▶ │ Browser  │
│ + Browser (Python)   │ ───────────▶ │ Playwright (JS) server │                        │ process  │
│  keywords            │ ◀─────────── │  + gRPC server        │ ◀───────────────────── │          │
└─────────────────────┘               └──────────────────────┘     (WebSocket/pipe)     └──────────┘
        ▲                                       ▲
        │ Plugin API (Python)                   │ jsextension / call_js_keyword (JS)
        │                                        │
   you can add Python keywords here        you can add JS that runs inside the Node process
                                            with direct access to Playwright `page` objects
```

Key consequences:

- Python-side code (keywords, plugins) talks to the browser **only** by issuing gRPC calls
  to the Node process. It never holds a Playwright object directly.
- JS-side extensions (`jsextension`) run **inside the Node process** and receive the live
  Playwright `page`, `context`, `browser`, and a `playwright` handle. This is the only place
  Playwright objects are directly reachable.
- Neither side is handed a WebDriver BiDi session, because Playwright doesn't create one in
  normal operation.

### 2.2 Mechanism A — `jsextension` (CommonJS JS module)

```javascript
// mymodule.js
async function myGoToKeyword(url, page, logger) {
    logger("Going to " + url);
    return await page.goto(url);
}
myGoToKeyword.rfdoc = "This is my own go to keyword";
exports.__esModule = true;
exports.myGoToKeyword = myGoToKeyword;
```
```robotframework
*** Settings ***
Library    Browser    jsextension=${CURDIR}/mymodule.js
```

- Functions receive `(args..., page, logger)` and run **inside the Node process** with direct
  Playwright object access.
- Return values must be **JSON-serialisable** to cross gRPC back to Python.
- Good for: short Playwright-native operations (`page.mouse.wheel`, CDP session via
  `context.newCDPSession(page)`, route interception). Most extensions in the mono-repo
  (Throttle_Network, mockUrl, Playwright-page-methods) use this.
- Bad for: long-lived connections, persistent event subscriptions, anything needing its own
  WebSocket lifecycle and an asyncio/event loop that outlives a single keyword call.

### 2.3 Mechanism B — Plugin API (Python class) — **recommended for BiDi**

```python
from robot.api.deco import keyword
from Browser.base.librarycomponent import LibraryComponent
from Browser import Browser

class Plugin(LibraryComponent):
    def __init__(self, library: Browser, *args, **kwargs):
        super().__init__(library)
        # optional: self.initialize_js_extension(Path(__file__).parent / "helper.js")

    @keyword
    def my_python_keyword(self):
        # full Python; can call other Browser keywords via self.library.<keyword>
        return self.library.evaluate_javascript(None, "window.location")
```
```robotframework
*** Settings ***
Library    Browser    plugins=${CURDIR}/Plugin.py
```

- Imported like a Robot library; **multiple** allowed (comma-separated); supports
  positional/`*args`/`**kwargs` constructor arguments (semicolon-separated in the import).
- The class inherits `LibraryComponent`, giving access to:
  - `self.library` — the full Browser public Python API (call any keyword as a method).
  - `self.call_js_keyword(name, **kwargs)` — call a private JS function bundled via
    `initialize_js_extension(...)` (JS that is *not* exposed as an RF keyword).
  - the library's logging, run-on-failure, and lifecycle hooks.
- Keywords are tagged `plugin` automatically, so libdoc separates them.
- **This is the correct home for a BiDi extension**: it can own a Python asyncio BiDi client,
  manage its lifecycle across the suite, expose clean keywords, and still drop into JS via
  `call_js_keyword` when it needs Playwright-side correlation data (e.g. the CDP target id or
  the browser's WebSocket debugger URL).

### 2.4 Mechanism C — A separate library built on top of Browser

A standalone `robotframework-browserbidi` library that the user imports *alongside* Browser.
Viable, but loses the tight lifecycle integration (shared browser handle, run-on-failure,
single import) that the Plugin API gives for free. Recommended only if the project later
outgrows the plugin model.

**Decision:** Use the **Plugin API** (Mechanism B), optionally with a small bundled JS helper
(`initialize_js_extension`) used purely to fetch correlation metadata from Playwright.

---

## 3. The protocol reality: Playwright vs. CDP vs. WebDriver BiDi

This section is the crux of the feasibility question.

### 3.1 What WebDriver BiDi is

WebDriver BiDi is a **W3C standard-in-progress** for bidirectional browser automation. Unlike
classic WebDriver (HTTP request/response), BiDi uses a **WebSocket** carrying JSON-RPC-style
messages, so the browser can **push events** (network, log, script, browsingContext) to the
client in real time. It is positioned as the cross-browser successor to CDP, combining
WebDriver's standardisation with CDP's depth. As of early 2026 it is supported (to varying
degrees) by **Chrome, Edge, and Firefox**; **Safari/WebKit support is not yet available**.

Relevant BiDi modules for "extra data":

- `network` — `responseStarted`, `responseCompleted`, `beforeRequestSent`, `fetchError`, and
  crucially **response body retrieval** (a long-standing gap in CDP-via-Playwright ergonomics).
- `log` — `entryAdded` for console messages and **uncaught JS exceptions** with full stack
  traces and source location.
- `script` — `evaluate` / `callFunction` in a specified **realm** (including sandbox realms),
  `addPreloadScript`, plus `realmCreated`/`realmDestroyed` events.
- `browsingContext` — tree, navigation events, `userPromptOpened`, screenshot, `print`.
- `session` — `subscribe`/`unsubscribe` to event types, capability negotiation.

### 3.2 Where Playwright sits

Playwright does **not** use WebDriver BiDi as its production protocol. It drives Chromium via
**CDP** and Firefox/WebKit via **patched/custom protocols**. There was an **experimental** BiDi
effort (PR in 2024; ongoing Mozilla collaboration to close feature gaps such as user contexts
and emulation), but:

- It is reachable only through **internal, unstable channel identifiers** in Playwright's own
  test harness (`tests/bidi`, run via `npm run biditest`, env vars `BIDI_FFPATH`/`BIDI_CRPATH`).
- There is **no public Playwright API** of the form `browser.bidiSession()` or
  `page.bidi`. Nothing in the public surface returns a usable BiDi connection.
- Browser library pins a specific Playwright version and exposes Playwright only indirectly via
  gRPC; even if a hidden BiDi handle existed, the gRPC bridge does not surface it.

**Conclusion:** You **cannot** obtain a BiDi session by reaching *through* Browser → Node →
Playwright. Any design that assumes "ask Playwright for its BiDi connection" is a dead end.

### 3.3 What *is* reachable: CDP via Playwright

Playwright *does* expose CDP on Chromium: in JS, `context.newCDPSession(page)` returns a
`CDPSession` you can `.send(...)`/`.on(...)`. The Browser library's own `Connect To Browser`
supports `use_cdp=True` against a `--remote-debugging-port` endpoint. So a **CDP-based**
extension is trivially feasible *through the existing plumbing* (via a `jsextension`).
The trade-off: CDP is **Chromium-only** and **non-standard**. That is acceptable for many
"extra data" needs but does not deliver the cross-browser, standards-based promise of BiDi.

### 3.4 The viable BiDi path: a parallel session to the same browser

The realistic way to get *true BiDi* data is to open a **second, independent connection** —
a BiDi WebSocket — to the **same browser process** that Playwright is already driving, then
correlate the two by target/context.

There are two sub-strategies depending on how the browser was launched:

**Strategy 1 — Browser launched by you with BiDi enabled, Playwright connected over CDP.**
1. Launch the browser yourself (Chromium for Testing / Firefox beta) with both a CDP debugging
   port *and* BiDi enabled (Chromedriver/Geckodriver can expose the `webSocketUrl` BiDi
   endpoint; Chromium also exposes BiDi over its `/session` negotiation).
2. Point Browser at it: `Connect To Browser    http://localhost:<port>    use_cdp=True`.
3. The extension opens its **own** BiDi WebSocket to the same instance, runs `session.new` /
   `session.subscribe`, and streams events.
4. Correlate Playwright pages ↔ BiDi `browsingContext` ids using the URL + target id (read the
   target id on the Playwright side via a tiny CDP call in a `jsextension`).

**Strategy 2 — Chromium-only shortcut via CDP's BiDi mapper.** Chromium ships a
**BiDi-over-CDP "mapper"** (the same mechanism `chromedriver` uses to provide BiDi). The
extension can attach to the existing CDP endpoint and speak BiDi through the mapper, avoiding a
second browser launch. This keeps a single browser/single endpoint but is **Chromium-only** and
couples you to the mapper's quirks.

**Recommended default:** **Strategy 1** for the cross-browser story (the whole point of BiDi),
with **Strategy 2** offered as a Chromium-only "low-friction" mode.

---

## 4. Does this actually add data beyond Playwright? (Value analysis)

Yes — concretely. The table maps desired data to what Playwright/Browser already gives vs. what
the BiDi side-channel adds.

| Capability | Playwright / Browser today | BiDi side-channel adds |
|---|---|---|
| Network request/response metadata | `Wait For Response`, route handlers (per-call, wrapper-shaped) | Continuous `network.responseCompleted` stream with timings, sizes, cache state |
| **Network response bodies** (post-load, reliably) | Awkward; must intercept *before* the response or re-fetch | First-class body retrieval via BiDi network module (a headline BiDi feature) |
| Console logs / JS errors | `Get Console Log` (wrapped, lossy ordering across contexts) | Raw `log.entryAdded` with level, args, stack, source, timestamp, realm |
| Uncaught exceptions w/ stack | partial | Full structured stack + source location |
| Event subscription model | callback wrappers, mostly per-keyword | Native `session.subscribe` to event classes for the whole run |
| Realm/sandbox script evaluation | `Evaluate JavaScript` (main world) | `script.evaluate` in arbitrary realms incl. isolated sandboxes |
| Cross-browser consistency of the above | CDP-shaped on Chromium, different on FF/WebKit | Standardised shape across Chrome/Edge/Firefox |
| Preload scripts (run before page scripts) | `Add Init Script` (Playwright wrapper) | `script.addPreloadScript` with realm targeting |

Where Playwright is already adequate (clicking, locators, screenshots, basic waits), the
extension should **not** duplicate it. The extension's value is the **observability/data layer**,
not re-implementing interaction.

> Caveat to set expectations honestly: several of these (notably response bodies and console
> capture on Chromium) are *also* obtainable via CDP. The unique, non-CDP justification for BiDi
> is (a) **cross-browser** uniformity, especially **Firefox**, and (b) **standards alignment**
> as CDP is progressively deprecated in favour of BiDi. If the project only ever targets
> Chromium, a CDP extension is simpler and a BiDi extension is harder to justify. The
> recommendation assumes cross-browser (esp. Firefox) data capture is a real requirement.

---

## 5. Recommended architecture

### 5.1 Component overview

```
robotframework-browser (Browser)  ──gRPC──▶  Node/Playwright  ──CDP──▶  Browser process
        │                                                                     ▲
        │ plugins=BrowserBiDi.py                                              │
        ▼                                                                     │ BiDi WebSocket
┌────────────────────────────────────────────┐                              │ (independent)
│ BrowserBiDi (Plugin, LibraryComponent)       │                              │
│  • owns asyncio BiDi client + event loop      │ ─────────────────────────────┘
│  • session.new / subscribe / event buffers   │
│  • correlation: page URL/targetId ↔ context  │  ◀── tiny jsextension reads Playwright targetId
│  • RF keywords (Get BiDi ..., Wait For BiDi ...)│
└────────────────────────────────────────────┘
```

### 5.2 The BiDi client

Two options:

- **Reuse an existing Python BiDi client.** Lower maintenance; inherits upstream protocol
  updates. Verify license compatibility (the extensions repo is Apache-2.0) and maintenance
  health before depending on it.
- **Ship a minimal in-house client** (~a few hundred lines: a `websockets`-based JSON-RPC
  duplex with an id→future map, an event dispatcher, and typed wrappers for the
  `session`/`network`/`log`/`script`/`browsingContext` commands actually used). More control,
  no external dependency drift, but you own protocol churn.

**Recommendation:** Start with a **thin in-house client** scoped to only the modules used (§3.1),
because BiDi is still evolving and a small surface is cheaper to keep correct than tracking a
general-purpose dependency. Keep it isolated behind an interface so it can be swapped for a
third-party client later.

### 5.3 Event-loop and lifecycle strategy

- Run the BiDi client in a **dedicated asyncio loop on a background thread**, owned by the
  plugin instance. Robot keywords are synchronous; they push coroutines onto that loop with
  `run_coroutine_threadsafe(...)` and block for the result. This keeps the persistent WebSocket
  and event subscriptions alive across keyword calls without blocking Robot's main thread.
- Maintain **bounded event buffers** (e.g. `collections.deque(maxlen=N)` per event class) so
  long runs don't leak memory; expose keywords to drain/filter them.
- Tie connect/disconnect to the **plugin lifecycle** and to Browser's
  `New Browser`/`Connect To Browser`/`Close Browser`. Practical approach: a `Connect BiDi`
  keyword the user calls right after connecting Browser, plus best-effort auto-teardown on
  `Close Browser` (subscribe to library shutdown / use `__del__`/`atexit` defensively).

### 5.4 Correlation between Playwright pages and BiDi contexts

The hard part. Approach:

1. On the Playwright side, a bundled JS helper (loaded via `initialize_js_extension`) reads the
   active page's **CDP target id** and **URL** (`context.newCDPSession(page)` →
   `Target.getTargetInfo`, or `page.url()`).
2. On the BiDi side, `browsingContext.getTree` lists contexts with ids and URLs.
3. Match by target id where the transport allows it (Chromium target id ≈ BiDi context id under
   the mapper), else fall back to URL + creation order. Cache the mapping; refresh on navigation.
4. Expose a keyword `Get BiDi Context For Current Page` so advanced users can target explicitly.

This is the main source of fragility and should be covered by integration tests per browser.

---

## 6. Proposed keyword surface (initial)

Keep it small, observability-focused, and non-overlapping with Browser. All keywords carry the
auto-applied `plugin` tag.

Connection / session
- `Connect BiDi    bidi_url=<ws-url>    [browser=chromium|firefox]    [auto_subscribe=...]`
- `Disconnect BiDi`
- `BiDi Subscribe    events=network.responseCompleted,log.entryAdded,...`
- `BiDi Unsubscribe    events=...`
- `Get BiDi Context For Current Page` → context id

Network
- `Get BiDi Network Events    [url_glob=]    [since=]` → list of structured events
- `Get BiDi Response Body    request_id` → bytes/text (the headline capability)
- `Wait For BiDi Response    url_glob    [timeout=]` → event

Logs / errors
- `Get BiDi Console Log    [level=]    [since=]`
- `Get BiDi JS Errors    [since=]` → structured stack traces
- `Wait For BiDi Log Entry    matcher    [timeout=]`

Script / realm
- `BiDi Evaluate    expression    [realm=]    [context=]`
- `BiDi Add Preload Script    function_body`

Each returns plain JSON-serialisable Python (dicts/lists) so it composes with standard Robot
assertions and `Should Be ...` keywords.

### 6.1 Example usage

```robotframework
*** Settings ***
Library    Browser    plugins=${CURDIR}/BrowserBiDi.py

*** Test Cases ***
Capture Real Network Bodies Across Browsers
    Connect To Browser    http://localhost:9222    use_cdp=True
    Connect BiDi          ws://localhost:9222/session    browser=chromium
    BiDi Subscribe        events=network.responseCompleted, log.entryAdded
    New Page              https://example.com/app
    ${resp}=    Wait For BiDi Response    **/api/profile
    ${body}=    Get BiDi Response Body    ${resp}[request][request_id]
    Should Contain        ${body}    "userId"
    ${errors}=  Get BiDi JS Errors
    Should Be Empty       ${errors}
    [Teardown]    Run Keywords    Disconnect BiDi    AND    Close Browser
```

---

## 7. Risks, limitations, and honest caveats

1. **Playwright gives you nothing here.** All BiDi value comes from a *parallel* connection you
   manage. If the browser wasn't launched with BiDi reachable, the extension can't function —
   so the launch/connect story must be documented tightly and ideally helped by a launcher
   keyword.
2. **Two clients, one browser.** Running Playwright (CDP) and your BiDi client against the same
   instance simultaneously can race or contend on the same targets. Mitigate by using BiDi for
   **read/observe** operations and leaving **mutation/interaction to Playwright**. Avoid issuing
   conflicting commands (e.g., both navigating).
3. **Browser coverage is uneven.** Chrome/Edge/Firefox: yes (to varying maturity).
   **WebKit/Safari: no BiDi.** The extension must degrade gracefully and document this.
4. **Spec churn.** BiDi is still pre-final; event/command shapes change. The thin-client
   approach localises the blast radius, but expect maintenance.
5. **Correlation fragility** (page ↔ context). Needs per-browser integration tests and a manual
   override keyword.
6. **Lifecycle/threading bugs** are the most likely source of flakiness (orphaned loops,
   unclosed sockets on crash). Invest in robust teardown and `atexit` safety nets.
7. **Overlap with CDP.** On Chromium-only projects, a CDP extension delivers ~80% of the value
   with far less complexity. Be explicit that BiDi's differentiator is **cross-browser +
   standards-future-proofing**, primarily for **Firefox** data capture.

---

## 8. Recommendation and phased plan

**Recommendation:** Proceed, but scope it as an **observability side-channel**, packaged as a
**Browser Plugin** named e.g. `Browser-BiDi`, contributed to
`robotframework-browser-extensions`. Do **not** attempt to route BiDi through Playwright.

**Phase 0 — Spike (1–2 days).** Manually launch Chromium-for-Testing with CDP + BiDi reachable;
from a standalone Python script, open a BiDi WebSocket, run `session.new` + `session.subscribe`
for `log.entryAdded` and `network.responseCompleted`, and retrieve one response body. Confirm
the same against Firefox (Geckodriver `webSocketUrl`). This validates the entire premise before
any Robot integration. **Kill criterion:** if a parallel BiDi session can't coexist with a
Playwright CDP session on the same instance, stop or pivot to a separate-library / launch-two
model.

**Phase 1 — Plugin skeleton.** `LibraryComponent` plugin + background asyncio loop + thin BiDi
client (session/network/log only) + `Connect BiDi`/`Disconnect BiDi`/`BiDi Subscribe` +
`Get BiDi Network Events`/`Get BiDi Response Body`/`Get BiDi Console Log`. Chromium first.

**Phase 2 — Correlation + Firefox.** JS helper for target id, page↔context mapping,
`Get BiDi Context For Current Page`, Firefox via Geckodriver, integration tests per browser.

**Phase 3 — Script/realm + polish.** `BiDi Evaluate`, `BiDi Add Preload Script`,
`Wait For BiDi ...` keywords, bounded buffers, libdoc docs, example suite, README in the
mono-repo style, run-on-failure integration.

**Phase 4 — Upstream alignment.** Track Playwright's BiDi maturation; if/when Playwright exposes
a stable public BiDi session, evaluate folding the side-channel into the native plumbing and
deprecating the parallel connection.

---

## 9. Appendix — quick reference of facts grounding this proposal

- Browser library = Python RF library ⇄ **gRPC** ⇄ Node.js process running **Playwright (JS)**;
  every keyword is a gRPC call; the browser may even be on another host but the Node process
  runs alongside RF.
- Three extension routes: **Plugin API** (Python, `LibraryComponent`, `@keyword`, `plugins=`),
  **jsextension** (CommonJS JS, runs in Node with live `page`), **separate library** on top.
- Plugins get `self.library` (full Browser API), `self.call_js_keyword`, `initialize_js_extension`,
  auto `plugin` tag; multiple plugins importable; constructor args via `;`.
- Playwright transport: **CDP** on Chromium; patched protocols on FF/WebKit. **BiDi support is
  experimental/internal** (test harness `tests/bidi`, `npm run biditest`, `BIDI_FFPATH`/
  `BIDI_CRPATH`); **no public BiDi API**.
- Browser's `Connect To Browser ... use_cdp=True` connects to a `--remote-debugging-port`
  endpoint (Chromium-only); `Launch Browser Server` exists for PW server mode.
- WebDriver BiDi: W3C standard-in-progress; **WebSocket**, bidirectional, pushes events;
  modules incl. `session`, `network` (with **response bodies**), `log`, `script` (realms,
  preload), `browsingContext`. Supported in **Chrome/Edge/Firefox**; **no Safari/WebKit** yet;
  positioned as CDP's cross-browser successor.
