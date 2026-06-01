## Why

The Robot Framework `Browser` library drives browsers through Playwright (over gRPC → Node → CDP), which exposes only a lossy, wrapper-shaped subset of browser observability data and does **not** expose a usable WebDriver BiDi session. Test authors who need standards-based, cross-browser observability — real network response bodies, raw console/JS-exception streams, realm-scoped evaluation — have no way to get it through the existing plumbing, especially on Firefox.

We can close this gap now by opening an **independent BiDi WebSocket** to the *same* browser instance Playwright already drives, exposing BiDi-only data as new Robot Framework keywords. This is feasible today (Playwright's own BiDi support is internal/unstable and unreachable through the gRPC bridge), and BiDi is the W3C-standard successor to CDP, so the investment is future-proof.

## What Changes

- Introduce `Browser-BiDi`, a **Browser library Plugin** (Python class inheriting `LibraryComponent`) for the `robotframework-browser-extensions` mono-repo, packaged so users add it via `Library Browser plugins=BrowserBiDi.py`.
- Add a **side-channel BiDi client**: a thin in-house `websockets`-based JSON-RPC duplex (scoped to the `session`/`network`/`log`/`script`/`browsingContext` modules) running on a dedicated asyncio loop on a background thread, owned by the plugin.
- Add keywords to **connect/disconnect** a parallel BiDi session and **subscribe/unsubscribe** to event classes for the whole run, plus an optional launcher helper for a BiDi-reachable browser.
- Add **network observability** keywords: continuous event capture and first-class **response body retrieval**.
- Add **log/error observability** keywords: raw `log.entryAdded` console capture and structured uncaught-exception stack traces.
- Add **realm script evaluation** keywords: `script.evaluate`/`callFunction` in arbitrary realms and `addPreloadScript`.
- Add **page ↔ BiDi context correlation** (via a tiny bundled `jsextension` that reads the Playwright target id) with a manual-override keyword.
- The extension is **observability-only**: it does not duplicate Playwright interaction (clicking, locators, navigation), which remain Playwright's responsibility to avoid two clients racing on the same browser.

## Capabilities

### New Capabilities
- `bidi-session-management`: Establish, configure, and tear down an independent BiDi WebSocket session to the running browser; event subscription lifecycle; background asyncio loop and bounded event buffers; optional BiDi-reachable browser launch helper.
- `bidi-page-correlation`: Map Playwright pages to BiDi `browsingContext` ids (by target id, falling back to URL + creation order) with caching and a manual-override keyword.
- `bidi-network-observability`: Capture network events (timings, sizes, cache state) and retrieve response bodies via the BiDi network module.
- `bidi-log-observability`: Capture raw console log entries and structured uncaught JS exceptions with stack traces and source locations.
- `bidi-script-evaluation`: Evaluate expressions/functions in arbitrary realms (including sandboxes) and register preload scripts via the BiDi script module.
- `bidi-getter-assertions`: Getter keywords with inline assertions (Browser-library / `robotframework-assertionengine` pattern) for QA-relevant BiDi data — response status/headers/body, network counts/timings, console/JS-error counts, URL/title/DOM snapshot, cookies, elements (incl. open shadow DOM via `pierce_shadow` and iframes via context), Web Vitals, and screenshots — plus driverless BiDi launching where supported (Firefox native; Chrome via the chromium-bidi mapper).

### Modified Capabilities
<!-- None — this is a greenfield extension; no existing specs change. -->

## Impact

- **New package**: `Browser-BiDi` plugin in `robotframework-browser-extensions` (Apache-2.0). New Python module(s) for the plugin and thin BiDi client; a small bundled `jsextension` helper for correlation metadata.
- **Dependencies**: adds `websockets` (or equivalent async WebSocket lib); requires the `robotframework-browser` (`Browser`) library as host.
- **Runtime/launch contract**: users must launch or connect to a browser with **both** a CDP debugging endpoint (for Playwright/`Connect To Browser use_cdp=True`) **and** BiDi reachable; this constraint must be documented and ideally assisted by a launcher keyword.
- **Browser coverage**: Chrome/Edge/Firefox supported (varying maturity); **WebKit/Safari has no BiDi** and must degrade gracefully.
- **Risk surface**: two clients on one browser (mitigated by read-only BiDi use), correlation fragility (per-browser integration tests), BiDi spec churn (localised by the thin client), and asyncio loop/socket lifecycle teardown.
