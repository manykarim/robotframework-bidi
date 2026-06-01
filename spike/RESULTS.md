# Phase 0 + Integration results

Executed 2026-05-29 on Linux x86_64 against real browsers.

**Environment:** Chrome 147.0.7727.116 + ChromeDriver 147.0.7727.117 · Firefox 150.0
+ geckodriver 0.36.0 · robotframework-browser 19.12.5 · robotframework 7.4.2 ·
websockets 16.0 · Python 3.12.

## Phase 0 spike — Chromium (tasks 1.1–1.3, 1.5) ✅ PASS

`spike/run_phase0_chromium.py` → `rc=0`:
- Launched Chromium via chromedriver exposing **both** a BiDi `webSocketUrl` **and** a
  CDP `debuggerAddress` on the same instance.
- `session.new` correctly **auto-skipped** (driver webSocketUrl is a pre-established
  session) — best-effort handling validated.
- `session.subscribe` to `log.entryAdded` + `network.responseCompleted` worked.
- `network.responseCompleted` captured; **response body retrieved (528 chars)** after
  registering `network.addDataCollector`.
- **Kill criterion (1.5) NOT triggered:** a parallel BiDi session coexists with the CDP
  endpoint on the same browser.

## Production-manager integration — Chromium ✅ 8/8

`run_integration.py` (real `BiDiManager`): connect+auto-subscribe, collector registered,
network events, response body (528 chars), console log capture, URL correlation, `BiDi
Evaluate`==42, clean disconnect — all PASS.

## Full Robot suite — Chromium (task 6.6) ✅ 3/3

`tests/integration/test_chromium.robot` with Playwright driving over CDP **and**
Browser-BiDi observing the same browser (complete Strategy 1):
- Connect And Resolve Context For Current Page — PASS (jsextension target-id correlation)
- Capture Network Events And Body — PASS
- Capture Console Log — PASS (BiDi captures a Playwright-emitted console.log)

## Firefox (task 1.4) — ⚠️ BiDi-level PASS; full Strategy-1 NOT achievable via Browser

`spike/run_firefox.py` → **6/6** at the BiDi client level: connect+subscribe, network
events, console log, **URL-based correlation** (no CDP target id → URL fallback, as
designed), `BiDi Evaluate`==42, clean disconnect.

**Findings / limitations (honest):**
1. **No full Strategy-1 on Firefox via Browser.** Firefox has no CDP, and Browser/
   Playwright cannot attach to an externally launched Firefox — it launches its *own*.
   So the BiDi session and Playwright end up on *different* Firefox instances; they can't
   share contexts/logs. The `test_firefox.robot` suite therefore fails by design and is
   marked as documenting this limitation. Firefox value is realised at the BiDi-client
   level (validated above), pending a way to point Playwright at an external Firefox.
2. **Response bodies unreliable on Firefox.** `network.getData` errors on compressed
   streams (`NS_ERROR_FAILURE` in `decodeCompressedStream`). The extension degrades
   gracefully with a clear error. Response bodies are **Chromium-reliable**.

## Code fixes driven by these runs

- `session.new` made best-effort (driver webSocketUrl is pre-established).
- `network.addDataCollector` added + wired into connect — required before responses or
  bodies aren't retained (`No collected response data`).
- Launcher: wait for driver `/status` readiness before `POST /session`; terminate the
  driver on handshake failure; **DELETE the WebDriver session on close** so geckodriver
  quits Firefox (it does not on plain terminate) — no orphaned browsers.

## Getter / Assertion keywords — Chromium ✅ 19/19

`run_getters.py` (real `BiDiManager`) validated: response status/headers, network
event count, resource timings, url, title, DOM snapshot, element count/text, web
vitals, cookies, screenshot, accessibility locator, **shadow-DOM piercing**
(`pierce_shadow=True`), and **iframe** isolation/targeting (separate context).
The full Robot example (`examples/bidi_example.robot`) passes 3/3 with the
getter+assertion keywords through Playwright-over-CDP + BiDi coexistence.

Findings:
- `browsingContext.locateNodes` with CSS does **not** cross shadow boundaries;
  shadow DOM reading uses a script-based deep query (`pierce_shadow=True`).
- Iframes are separate browsing contexts; pass the child `context` id.

## Do you need a WebDriver? — driverless BiDi (2026-05-29)

- **Firefox: driverless BiDi confirmed.** `firefox --remote-debugging-port=PORT
  --remote-allow-origins=*` prints `WebDriver BiDi listening on ws://host:PORT`;
  connecting to `ws://host:PORT/session` + `session.new` works (getTree → real
  contexts; navigate + title + element count validated via the production
  manager). **No geckodriver.** `launch_firefox()` now does this by default and
  kills the whole process group on close (no orphans).
- **Chrome: NOT driverless.** Chrome's `--remote-debugging-port`
  `/devtools/browser` socket is **CDP only** — `session.new` →
  `{"error":{"code":-32601,"message":"'session.new' wasn't found"}}`, and
  `/session` → 404. BiDi needs the **chromium-bidi mapper** (chromedriver bundles
  it; Puppeteer runs it client-side). `launch_chromium()` keeps using chromedriver.
- **Client bug found & fixed:** the BiDi client only recognized BiDi-style errors
  (`{"type":"error",...}`) and silently swallowed CDP-style errors
  (`{"error":{...}}`) as empty results — so a wrong (CDP) endpoint looked like an
  empty success. Now both shapes raise `BiDiError`.

## Driverless Chrome via chromium-bidi mapper (task 9.10) ✅

Reproduced chromedriver's internal technique in pure Python (no chromedriver, no
Node): load the vendored `chromium-bidi` mapper bundle into a hidden Chrome tab
over CDP and proxy BiDi through it (`Browser_BiDi/mapper_client.py`).

Bootstrap: `Target.attachToBrowserTarget` → `Target.createTarget` (hidden) →
`Target.attachToTarget` (flatten) → `Runtime.enable` →
`Target.exposeDevToolsProtocol bindingName=cdp` → `Runtime.addBinding
sendBidiResponse` → `Runtime.evaluate <mapper>` → `runMapperInstance(targetId)`.
Send BiDi via `Runtime.evaluate onBidiMessage("…")`; receive via
`Runtime.bindingCalled`.

- `run_mapper.py` (NO chromedriver on PATH) → **7/7**: connect via mapper, data
  collector, navigate, title, element count, network capture, response status,
  **response body**.
- Full plugin Strategy-1 **driverless**: `examples/bidi_example.robot` with
  Playwright over CDP **and** BiDi-via-mapper on the *same* Chrome passes 3/3.
  Caveat: with the client-side mapper, the *first* Playwright-driven navigation
  immediately after connect can occasionally race the mapper enabling network
  tracking on the new target (intermittent; subscribe-before-navigate + the
  buffer check make it reliable in practice).
- Mapper version must roughly track Chrome; validated chromium-bidi 16.0.1 +
  Chrome 147.

Both browsers are now driverless: **Firefox** native (`launch_firefox()`),
**Chrome** via the bundled mapper (`launch_chromium_driverless()` +
`transport=cdp-mapper`). chromedriver/geckodriver paths remain optional.

## How to reproduce

```bash
# drivers on PATH (matching browser versions):
python spike/run_phase0_chromium.py          # Chromium Phase 0
python spike/run_firefox.py                   # Firefox BiDi-level
# Full Robot (launch a dual-endpoint browser, pass CDP_URL/BIDI_URL):
robot --variable CDP_URL:... --variable BIDI_URL:... tests/integration/test_chromium.robot
```
