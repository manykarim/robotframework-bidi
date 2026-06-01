# WebDriver BiDi for Web Application Testing

**An analysis of testing-relevant capabilities and a proposal for Robot Framework integration**

Source specification: WebDriver BiDi, W3C Editor's Draft (11 May 2026) — <https://w3c.github.io/webdriver-bidi/>
Context: Robot Framework, with Browser Library (Playwright) and SeleniumLibrary

---

## 1. Executive summary

WebDriver BiDi adds bidirectional, event-streaming communication on top of the classic command/response WebDriver protocol. Instead of polling the browser, a test client subscribes to events that stream from the browser as things happen. This better matches the evented nature of the DOM and unlocks testing capabilities that classic WebDriver never offered: network interception, real-time console/error capture, environment emulation, and proper test isolation.

For the Robot Framework ecosystem the implications differ sharply by library:

- **Browser Library** already provides most of these capabilities through Playwright's own protocol. For Browser Library users, BiDi is mainly relevant as a browser-agnostic, W3C-standard path rather than as new functionality.
- **SeleniumLibrary** is where the real opportunity lies. Selenium 4.x exposes BiDi, and these modules — especially `network`, `log`, and `emulation` — close the long-standing capability gap with Playwright using a standard protocol rather than Chromium-locked CDP hacks.

The recommendation is a thin, well-factored Robot Framework keyword layer over Selenium's BiDi support, mirroring Browser Library keyword naming where sensible so that suites remain portable between the two libraries.

**Caveat carried throughout:** this is an Editor's Draft. Several sections (notably sandbox realms in §5 and parts of `emulation` in §7.4) are recent or still marked with open issues. Implementation maturity differs between Firefox (most complete) and Chromium. Verify per-command support against target browser and Selenium versions before committing keyword designs.

---

## 2. How BiDi differs from classic WebDriver

Classic WebDriver is strictly synchronous: the client sends a command, the browser replies. There is no mechanism for the browser to notify the client that something happened. Tests therefore poll ("wait until element is visible", "wait until URL changes"), which is fragile for single-page applications and impossible for transient events like a console error or a specific network request.

BiDi introduces (spec §3):

- **Commands** (§3.4) — asynchronous operations that can run concurrently and finish out of order.
- **Events** (§3.6) — notifications pushed from the browser to the client, which the client subscribes to via `session.subscribe`.
- **Modules** (§3.3) — related commands and events grouped by concern (network, script, log, etc.).
- **WebSocket transport** (§4) — a persistent connection carrying both directions, JSON-RPC-like in shape.

This event model is the foundation for everything valuable below.

---

## 3. Modules with unique testing value (low overlap with current tooling)

These deliver capabilities that classic WebDriver cannot, and that justify adopting BiDi on their own merits.

### 3.1 `network` module — §7.5

The single most valuable module. Relevant to functionality, performance, and security testing.

**Events (§7.5.6):** `network.beforeRequestSent`, `responseStarted`, `responseCompleted`, `fetchError`, `authRequired`. These allow assertions on every request and response without an external proxy.

- The `network.FetchTimingInfo` type (§7.5.4.10) carries DNS, connect, TLS, and time-to-first-byte timings — directly useful for **performance** assertions such as "API call returns first byte under 500 ms".
- `responseCompleted` exposes status, headers, MIME type, transfer size, and whether the response came from cache.

**Intercepts and mocking (§7.5.3, §7.5.5):** `network.addIntercept` together with `continueRequest`, `continueResponse`, `provideResponse`, `failRequest`, and `continueWithAuth`. This is full request mocking and fault injection — stub a flaky third-party API, force a 500, simulate an auth challenge. This is the headline reason to adopt BiDi in Selenium-based suites, which historically required BrowserMob or mitmproxy to achieve the same thing.

**Data collection (§7.5.2):** `network.addDataCollector` plus `getData` collect response bodies for later assertion — good for functionality (validate JSON payloads) and security (inspect headers such as CSP, HSTS, and `Set-Cookie` flags via `network.SetCookieHeader`, §7.5.4.18).

`setCacheBehavior` and `setExtraHeaders` (§7.5.5.12–13) support caching-correctness tests and injection of auth or test headers.

### 3.2 `log` module — §7.8

Relevant to functionality and quality. The `log.entryAdded` event (§7.8.3.1) streams `console.*` output and uncaught JavaScript exceptions with stack traces (`script.StackTrace`). This is the cleanest way to fail a test on any unexpected console error — a strong proxy for page health. A test can subscribe globally and assert "zero error-level log entries during the journey", far more reliably than the brittle log-reading approaches classic Selenium required.

### 3.3 `script` module — §7.6

Relevant to functionality, security, and instrumentation.

- `script.evaluate` and `callFunction` (§7.6.4.3–4) — asynchronous JavaScript execution with proper serialization (`RemoteValue`, §7.6.3.14) and structured exception details, superior to classic JS execution.
- `script.addPreloadScript` (§7.6.4.1) — inject script *before* page scripts run. Use it to stub `Date` and `Math.random` for deterministic tests, install accessibility probes such as axe-core, or seed feature flags. This is the BiDi equivalent of Playwright's init scripts.
- Sandbox realms (§5) — run instrumentation in an isolated ECMAScript realm so probes do not collide with the application's globals. Important when injecting axe-core or performance observers without polluting the page. (Note: §5 is still partly specified with open issues.)
- The `script.message` event with channels (§7.6.3.1) — a page-to-test communication channel, useful for capturing custom telemetry the application emits.

### 3.4 `emulation` module — §7.4

A single module covering several non-functional dimensions: UX, design, accessibility, and performance.

- `setForcedColorsModeThemeOverride` (§7.4.2.1) — test Windows High Contrast / forced-colors rendering, a genuine **accessibility** requirement.
- `setGeolocationOverride`, `setLocaleOverride`, `setTimezoneOverride` (§7.4.2.2–3, .10) — test localization, i18n date and number formatting, and geo-gated UX without VPNs.
- `setNetworkConditions` (§7.4.2.4) — throttle and offline simulation for performance and offline-UX testing.
- `setScreenSettingsOverride`, `setScreenOrientationOverride`, `setScrollbarTypeOverride`, `setTouchOverride` (§7.4.2.5–6, .9, .11) — responsive design and mobile/touch UX validation.
- `setUserAgentOverride` (§7.4.2.7) — device and browser spoofing.
- `setScriptingEnabled` (§7.4.2.8) — test no-JavaScript graceful degradation.

### 3.5 `browsingContext` module — §7.3

Relevant to functionality, performance, and design.

- `captureScreenshot` (§7.3.3.2) and `print` to PDF (§7.3.3.9) — visual-regression inputs; `captureScreenshot` can feed directly into visual diffing (for example `robotframework-doctestlibrary`).
- `setViewport` (§7.3.3.12) — deterministic viewport sizing for visual tests.
- Navigation events (§7.3.4.3–12): `navigationStarted`, `domContentLoaded`, `load`, `navigationCommitted`, `navigationFailed`, `fragmentNavigated`, `historyUpdated`. Subscribe to these for accurate page-load performance timing and to detect SPA route changes that classic WebDriver waits miss.
- `downloadWillBegin` and `downloadEnd` (§7.3.4.8–9) with `browser.setDownloadBehavior` — proper download testing, historically painful in Selenium.
- `locateNodes` (§7.3.3.7) — protocol-level element location with `browsingContext.Locator` (CSS, XPath, inner text, and accessibility name/role). The accessibility locator is notable for a11y-aware element finding.
- User-prompt events and handling (§7.3.4.13–14, §7.3.3.6) — robust dialog handling via events rather than polling.

### 3.6 `input` module — §7.9

Relevant to functionality and UX. `performActions` (§7.9.3.1) provides the Actions API (pointer, key, and wheel sources) for realistic gestures: hover, drag-and-drop, multi-touch, and scroll-wheel. `setFiles` (§7.9.3.3) handles file uploads cleanly, and the `input.fileDialogOpened` event (§7.9.4.1) detects native file dialogs.

### 3.7 `storage` module — §7.7

Relevant to functionality and security. `getCookies`, `setCookie`, and `deleteCookies` with `storage.PartitionKey` (§7.7.2.1) provide partition-aware cookie inspection. Assert cookie security attributes (`Secure`, `HttpOnly`, `SameSite`) for security testing, and seed authentication cookies to skip login flows.

### 3.8 `browser` module — §7.2

Relevant to test isolation. `createUserContext` and `removeUserContext` (§7.2.4.2, .5) provide isolated browser contexts with separated cookies, storage, and cache — the BiDi equivalent of Playwright contexts. This is the right primitive for parallel, hermetic test isolation: each test or suite gets a clean `UserContext` instead of a fresh browser process.

### 3.9 `webExtension` module — §7.10

Specialized. `install` and `uninstall` (§7.10.3) support testing extension behavior or injecting testing extensions. Niche, but unique to BiDi.

---

## 4. Features that overlap Browser Library but remain valuable for SeleniumLibrary

Even where BiDi duplicates something Browser Library already does through Playwright, bringing it to SeleniumLibrary is worthwhile because it closes a real gap or replaces a fragile workaround. The honest filter below is "biggest delta from current SeleniumLibrary capability", not "biggest absolute feature".

| Feature (spec ref) | Browser Library today | SeleniumLibrary today | Value of BiDi for SeleniumLibrary |
|---|---|---|---|
| Console & JS error capture (`log`, §7.8) | Console events via Playwright | Unreliable, effectively Chrome-only, post-hoc | Real-time, cross-browser error + exception capture with stack traces |
| Network mocking & inspection (`network`, §7.5) | `Wait For Request/Response`, route mocking | Nothing native; external proxy required | Native stubbing, fault injection, and assertion without a proxy |
| Cookie & storage (`storage`, §7.7) | Rich context cookies/storage | Basic, no partition awareness | Partition handling, fuller attribute inspection, auth-cookie seeding |
| Geolocation / locale / timezone / color-scheme (`emulation`, §7.4) | `New Context` options | CDP-only, Chromium-locked, version-fragile | Standardized, cross-browser i18n / a11y / responsive emulation |
| Network throttling / offline (§7.4.2.4) | Context offline option | CDP-only hack | Standardized offline and throttling control |
| Viewport control (`browsingContext.setViewport`, §7.3.3.12) | Per-context viewport | Window resize (conflates chrome with viewport) | True viewport sizing; improves visual-test baseline reproducibility |
| Isolated contexts (`browser.createUserContext`, §7.2.4.2) | `New Context`, core feature | Fresh driver/process only (slow) | Fast, hermetic, isolated parallelism within one browser |
| Init/preload scripts (`script.addPreloadScript`, §7.6.4.1) | `Add Init Script` | No native equivalent; injection too late | True pre-page-script hooks for determinism and probe injection |
| Auth handling (`network.continueWithAuth`, §7.5.5.5 / `authRequired`, §7.5.6.1) | Context credentials | URL-embedded creds or extensions | Event-driven basic-auth handling |
| File uploads & downloads (`input.setFiles` §7.9.3.3; download events §7.3.4.8–9) | Handled well | Uploads awkward for hidden inputs; downloads awkward | Clean uploads, native-dialog detection, managed downloads |

For Browser Library users specifically, none of this is new functionality — the value there is only the W3C-standard, browser-agnostic protocol path. The real story is SeleniumLibrary reaching roughly Playwright-class capability on these dimensions using a standard rather than CDP.

---

## 5. Mapping to testing dimensions

| Dimension | Primary BiDi capabilities |
|---|---|
| Functionality | `network` events & data collection (§7.5), `script.evaluate`/`callFunction` (§7.6), `input.performActions` (§7.9), navigation events (§7.3.4), `storage` (§7.7) |
| Performance | `network.FetchTimingInfo` (§7.5.4.10), navigation timing events (§7.3.4.6–7), `emulation.setNetworkConditions` (§7.4.2.4) |
| UX | `emulation` locale/geo/timezone/touch (§7.4), `input.performActions` (§7.9), user-prompt events (§7.3.4.13–14) |
| Design / visual | `captureScreenshot` (§7.3.3.2), `print` (§7.3.3.9), `setViewport` (§7.3.3.12), `emulation` screen/orientation/scrollbar (§7.4) |
| Clarity / quality | `log.entryAdded` (§7.8) for console noise and uncaught errors |
| Accessibility | `emulation.setForcedColorsModeThemeOverride` (§7.4.2.1), accessibility locator in `locateNodes` (§7.3.3.7), axe-core injection via `addPreloadScript` (§7.6.4.1) |
| Security | `network` header/response inspection (§7.5), cookie attribute assertions via `storage` (§7.7), `network.continueWithAuth` (§7.5.5.5) |
| Test isolation | `browser.createUserContext` (§7.2.4.2) |

---

## 6. Prioritization

### 6.1 Unique-value modules (adopt first)

| Priority | Module | Why it earns its place |
|---|---|---|
| 1 | `network` (§7.5) | Mocking, fault injection, performance timings, security-header assertions — the biggest capability jump |
| 2 | `log` (§7.8) | Trivial to subscribe; catches JS errors and console noise across whole journeys |
| 3 | `emulation` (§7.4) | One module covers a11y (forced-colors), i18n, responsive, offline, and performance throttling |
| 4 | `script.addPreloadScript` + sandbox (§7.6, §5) | Deterministic tests plus clean a11y/perf probe injection |
| 5 | `browser.createUserContext` (§7.2) | Proper hermetic isolation for parallel suites |

### 6.2 Overlapping-but-worthwhile, ranked by SeleniumLibrary delta

| Tier | Feature | Delta for SeleniumLibrary |
|---|---|---|
| Must-have | `network` intercepts/events (§7.5) | From nothing to full mocking plus performance/security inspection |
| Must-have | `log.entryAdded` (§7.8) | From unreliable/post-hoc to streaming cross-browser error capture |
| Must-have | `createUserContext` (§7.2) | From process-per-isolation to fast hermetic contexts |
| High | `emulation` overrides (§7.4) | From CDP hacks to standardized i18n / a11y / offline |
| High | `addPreloadScript` (§7.6) | From too-late injection to true pre-page-script hooks |
| Medium | `setViewport` (§7.3) | From window-resize approximation to exact viewport |
| Medium | `storage` partition cookies (§7.7) | Refinement over existing cookie keywords |
| Medium | uploads/downloads (§7.9, §7.3) | From awkward to clean |

---

## 7. Proposal for Robot Framework

### 7.1 Goal

Provide a thin, well-factored Robot Framework keyword layer over Selenium's BiDi support that brings the high-value capabilities above into SeleniumLibrary-based suites, while keeping keyword naming aligned with Browser Library where sensible so that suites stay portable between the two libraries.

### 7.2 Scope and shape

- Target Selenium 4.x BiDi support as the transport. Expose BiDi modules through a focused set of keywords rather than a one-to-one wrapping of every command.
- Lead with the three must-have areas: network (intercept, mock, assert, timing), logging (subscribe, assert no errors), and isolated contexts.
- Follow with emulation overrides and preload-script injection.
- Keep keyword names recognizably close to Browser Library equivalents (for example a `Wait For Response`-style keyword and a route/intercept-style keyword) so test authors can move between libraries with minimal friction.

### 7.3 Why a separate, thin layer

- The event model is fundamentally different from SeleniumLibrary's synchronous keywords, so a dedicated layer keeps subscription lifecycle (subscribe, collect, assert, unsubscribe) explicit and testable rather than bolted awkwardly onto existing keywords.
- A thin layer can track the Editor's Draft as it stabilizes without destabilizing core SeleniumLibrary keywords.
- It fits naturally alongside existing MCP and agent-skills tooling: the same network/log subscription primitives are exactly what an AI agent needs to observe and reason about real execution rather than generated code.

### 7.4 Risks and mitigations

- **Spec maturity.** Editor's Draft; sandbox realms (§5) and parts of `emulation` (§7.4) carry open issues. *Mitigation:* gate each keyword behind a capability check and document per-browser support; ship network/log/context first since those are the most mature.
- **Engine divergence.** Firefox is the most complete BiDi implementation; Chromium support varies by command. *Mitigation:* maintain a support matrix and fail fast with clear messages when a command is unsupported on the active browser.
- **Overlap perception.** Browser Library already does most of this. *Mitigation:* position the work explicitly as a SeleniumLibrary capability-parity effort and a standards-based path, not a Browser Library competitor.

### 7.5 Suggested first milestone

A minimal keyword set proving the model end to end:

1. Subscribe to `log.entryAdded` and assert no error-level entries during a scenario.
2. Add a `network` intercept that mocks one endpoint and assert the page renders the mocked data.
3. Assert a `FetchTimingInfo`-derived TTFB threshold on a key request.
4. Run two scenarios in isolated `UserContext`s and confirm cookie/storage separation.

This exercises network, log, performance timing, and isolation — the four highest-value dimensions — in one coherent slice, and establishes the subscription lifecycle pattern the rest of the layer would reuse.

---

## 8. References

- WebDriver BiDi, W3C Editor's Draft, 11 May 2026 — <https://w3c.github.io/webdriver-bidi/>
- Latest published version — <https://www.w3.org/TR/webdriver-bidi/>
- Implementation report — <https://wpt.fyi/results/webdriver/tests/bidi>

All section references (§) in this document point to the Editor's Draft above. Because that draft is updated frequently, verify section numbers and command availability against the current revision before implementation.
