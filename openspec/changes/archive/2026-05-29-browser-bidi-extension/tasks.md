## 1. Phase 0 — Feasibility spike (kill criterion)

<!-- EXECUTED 2026-05-29 against real browsers (Chrome 147 / Firefox 150). Results in
     spike/RESULTS.md. Kill criterion NOT triggered on Chromium. -->
- [x] 1.1 Launch Chromium-for-Testing with both a CDP debugging port and BiDi reachable
- [x] 1.2 From a standalone Python script, open a BiDi WebSocket and run `session.new` + `session.subscribe` for `log.entryAdded` and `network.responseCompleted`
- [x] 1.3 Retrieve one response body via the BiDi network module
- [x] 1.4 Repeat 1.1–1.3 against Firefox using Geckodriver's `webSocketUrl` (BiDi-client level PASS; response body unreliable on FF — documented)
- [x] 1.5 Verify a parallel BiDi session can coexist with a Playwright CDP session on the same instance; **STOP/pivot if it cannot** (Chromium: coexists, full Robot suite 3/3. Firefox: full Strategy-1 not achievable via Browser — documented, scoped to BiDi-client level)

## 2. Package scaffold and thin BiDi client

- [x] 2.1 Create the `Browser-BiDi` package skeleton in the extensions mono-repo (Apache-2.0, mono-repo conventions)
- [x] 2.2 Add `websockets` (or equivalent) and `robotframework-browser` (host) dependencies
- [x] 2.3 Implement the thin BiDi client behind a swappable interface: `websockets` JSON-RPC duplex with an id→`Future` map
- [x] 2.4 Add the event dispatcher and typed command wrappers for `session` only (`new`/`subscribe`/`unsubscribe`)
- [x] 2.5 Add typed command wrappers for `network`, `log`, `script`, and `browsingContext` modules used by later phases
- [x] 2.6 Add unit tests for the JSON-RPC duplex, id→future correlation, and event dispatch

## 3. Plugin skeleton and session lifecycle

- [x] 3.1 Create the `Plugin(LibraryComponent)` class and wire it as `plugins=BrowserBiDi.py`
- [x] 3.2 Start a dedicated asyncio loop on a background thread owned by the plugin; add `run_coroutine_threadsafe` blocking bridge for sync keywords
- [x] 3.3 Implement `Connect BiDi` (ws url, browser hint, optional `auto_subscribe`) running `session.new`
- [x] 3.4 Implement `Disconnect BiDi` (unsubscribe all, close socket, stop loop) and best-effort auto-teardown on `Close Browser` / library shutdown with `atexit`/`__del__` safety nets
- [x] 3.5 Implement `BiDi Subscribe` / `BiDi Unsubscribe` over `session.subscribe`/`unsubscribe`
- [x] 3.6 Implement per-event-class bounded buffers (`deque(maxlen=N)`, configurable) with observable drop-oldest overflow
- [x] 3.7 Reject WebKit/Safari with a clear unsupported message; fail `Connect BiDi` with an actionable error when no BiDi endpoint is listening

## 4. Network observability (Chromium first)

- [x] 4.1 Buffer network events (`beforeRequestSent`, `responseStarted`, `responseCompleted`, `fetchError`)
- [x] 4.2 Implement `Get BiDi Network Events` with `url_glob` and `since` filters returning JSON-serialisable dicts
- [x] 4.3 Implement `Get BiDi Response Body` (by request id; text/bytes; clear error on unknown id)
- [x] 4.4 Implement `Wait For BiDi Response` (url glob + timeout) returning the matching event

## 5. Log / error observability

- [x] 5.1 Buffer `log.entryAdded` events preserving level, args, source, timestamp, realm
- [x] 5.2 Implement `Get BiDi Console Log` with `level` and `since` filters
- [x] 5.3 Implement `Get BiDi JS Errors` returning structured stack traces (empty list when none)
- [x] 5.4 Implement `Wait For BiDi Log Entry` (matcher + timeout)

## 6. Page ↔ context correlation and Firefox

- [x] 6.1 Bundle a `jsextension` helper (via `initialize_js_extension`) reading the page CDP target id and URL
- [x] 6.2 Implement correlation against `browsingContext.getTree` (match by target id, fallback to URL + creation order)
- [x] 6.3 Cache the mapping and refresh on navigation
- [x] 6.4 Implement `Get BiDi Context For Current Page` and explicit context-id override on observability keywords
- [x] 6.5 Add Firefox support via Geckodriver `webSocketUrl`
- [x] 6.6 Add per-browser integration tests (Chromium + Firefox) for correlation and core keywords (Chromium suite EXECUTED 3/3 PASS; Firefox suite documents the validated full-stack limitation, BiDi-level validated via spike/run_firefox.py)

## 7. Script / realm evaluation

- [x] 7.1 Implement `BiDi Evaluate` (expression/function in default or specified realm/context; surface script errors)
- [x] 7.2 Implement `BiDi Add Preload Script` via `script.addPreloadScript` with optional realm targeting

## 8. Launch helper, polish, and docs

- [x] 8.1 Provide a launcher helper that starts a browser exposing both CDP and BiDi endpoints (Chromium + Firefox) — EXECUTED + hardened (readiness wait, failure cleanup, session-delete on close so no orphaned browsers)
- [x] 8.2 Document the launch/connect contract and the read-only observe split (interaction stays with Playwright)
- [x] 8.3 Wire run-on-failure integration and finalize defensive teardown
- [x] 8.4 Generate libdoc, write the mono-repo-style README, and add an example Robot suite (mirroring proposal §6.1) — libdoc at `docs/keywords/Browser-BiDi.html`, README + `examples/bidi_example.robot` done
- [x] 8.5 Pin tested `Browser`/Playwright and browser versions for correlation stability (pinned `robotframework-browser>=19.12,<20`; tested versions recorded in README + spike/RESULTS.md)

## 9. Getter/Assertion keywords (AssertionEngine) + driverless

- [x] 9.1 Integrate `robotframework-assertionengine` (`verify_assertion`, `AssertionOperator`); add `serialization.py` for headers/cookies/timings/RemoteValue normalization (unit-tested)
- [x] 9.2 Add network getters: `Get BiDi Response Status/Headers/Body`, `Get BiDi Network Event Count`, `Get BiDi Resource Timings`
- [x] 9.3 Add log getters: `Get BiDi Console Log (Count)`, `Get BiDi JS Errors`/`JS Error Count` (assertion-enabled)
- [x] 9.4 Add page/DOM getters: `Get BiDi Url/Title/DOM Snapshot`, `Get BiDi Elements/Element Count/Element Text` (correlated-page scoped)
- [x] 9.5 Add storage/perf/snapshot: `Get BiDi Cookies` (storage.getCookies), `Get BiDi Web Vitals`, `Take BiDi Screenshot`
- [x] 9.6 Shadow DOM (`pierce_shadow`, css deep-query) + iframe (separate context) retrieval; keyword-only filters so positional assertion works
- [x] 9.7 Make filters keyword-only and resolve page-scoped getters to the correlated context; fix CDP-vs-BiDi error detection in the client
- [x] 9.8 Driverless launching: Firefox native BiDi (no geckodriver, process-group teardown); document Chrome-needs-mapper finding
- [x] 9.9 Unit tests (serialization + manager getters) and live validation (`spike/run_getters.py` 19/19, example suite 3/3, driverless Firefox); research notes (chrome-devtools-mcp, vibium) in spike/RESULTS.md
- [x] 9.10 Chrome driverless via client-side chromium-bidi mapper (no chromedriver): vendored `mapper/mapperTab.js` (Apache-2.0), `MapperBiDiClient` (CDP bootstrap + BiDi proxy), `Connect BiDi transport=cdp-mapper`, `launch_chromium_driverless()`; unit-tested (fake CDP) + live 7/7; full driverless Strategy-1 example 3/3. Firefox driverless already native (`launch_firefox()`).
