## Context

The Robot Framework `Browser` library is a Python RF library that talks **gRPC** to a long-lived **Node.js** process running **Playwright (JS)**, which drives the browser over **CDP** (Chromium) or patched protocols (Firefox/WebKit). Every keyword is a gRPC round-trip; Python-side code never holds a Playwright object. Playwright's own WebDriver BiDi support is **experimental and internal** (test harness `tests/bidi`, env vars `BIDI_FFPATH`/`BIDI_CRPATH`) with **no public API**, and the gRPC bridge does not surface it. Therefore a BiDi session cannot be obtained by reaching *through* Browser → Node → Playwright.

The viable path is a **side-channel**: open an independent BiDi WebSocket to the *same* browser instance Playwright is already driving, correlate the two by target/context, and expose BiDi-only data as new RF keywords. This must fit the `robotframework-browser-extensions` mono-repo conventions (Apache-2.0) and integrate with Browser's lifecycle. See `proposal.md` for motivation and `specs/` for normative requirements.

## Goals / Non-Goals

**Goals:**
- Deliver standards-based, **cross-browser** observability (esp. **Firefox**) that Playwright/Browser does not expose: network response bodies, raw console/JS-exception streams, realm-scoped evaluation, native event subscription.
- Package as a **Browser Plugin** (`LibraryComponent`) so it shares the library's lifecycle, logging, and single-import ergonomics.
- Keep the BiDi protocol surface **small and swappable** to localise spec-churn maintenance.
- Coexist safely with Playwright's CDP session on the same browser instance.

**Non-Goals:**
- Routing BiDi through Playwright/Browser's gRPC plumbing (proven infeasible).
- Re-implementing Playwright interaction (clicks, locators, navigation, screenshots). The extension is **observe/read-only**.
- WebKit/Safari support (no BiDi exists).
- A general-purpose, full-coverage BiDi client. Only the `session`/`network`/`log`/`script`/`browsingContext` modules actually used are implemented.

## Decisions

**D1 — Packaging: Plugin API (Mechanism B), not jsextension or separate library.**
A `LibraryComponent` subclass can own a persistent asyncio BiDi client and event loop across the suite, expose clean keywords (auto-tagged `plugin`), call `self.library.<keyword>`, and drop into JS via `call_js_keyword`/`initialize_js_extension` for correlation metadata. *Alternatives:* `jsextension` (rejected — runs per-keyword inside Node, cannot own a long-lived WebSocket/event loop); a standalone library on top of Browser (rejected for now — loses shared lifecycle, run-on-failure, single import; revisit only if the plugin model is outgrown).

**D2 — Side-channel session, not through-Playwright.**
Open an independent BiDi WebSocket to the same browser. Default **Strategy 1** (browser launched with both CDP port and BiDi reachable; Playwright connects over CDP, extension opens its own BiDi WS) for the cross-browser story. Offer **Strategy 2** (Chromium BiDi-over-CDP mapper, single endpoint) as a low-friction Chromium-only mode. *Rejected:* assuming `browser.bidiSession()` exists — it does not.

**D3 — Thin in-house BiDi client over a third-party dependency.**
~A few hundred lines: a `websockets`-based JSON-RPC duplex with an id→`Future` map, an event dispatcher, and typed wrappers for only the commands used. *Rationale:* BiDi is pre-final; a small surface is cheaper to keep correct than tracking a general-purpose dependency, and Apache-2.0 license compatibility/maintenance health of third-party clients is uncertain. Keep it **behind an interface** so a third-party client can be swapped in later. *Alternative:* reuse an existing Python BiDi client (lower maintenance but dependency drift + license risk).

**D4 — Dedicated asyncio loop on a background thread.**
RF keywords are synchronous; they push coroutines onto the plugin-owned loop with `run_coroutine_threadsafe(...)` and block for results. This keeps the persistent WebSocket and subscriptions alive across keyword calls without blocking RF's main thread. *Alternative:* per-keyword connect/disconnect (rejected — defeats event streaming and subscription model).

**D5 — Bounded event buffers.**
One `collections.deque(maxlen=N)` per event class, fed by the dispatcher; keywords drain/filter them. Prevents unbounded memory growth on long runs. Buffer sizes are configurable; overflow drops oldest and is observable.

**D6 — Correlation via bundled jsextension.**
A small JS helper loaded via `initialize_js_extension` reads the active page's CDP target id (`context.newCDPSession(page)` → `Target.getTargetInfo`) and URL. The BiDi side reads `browsingContext.getTree`. Match by target id where the transport allows (Chromium target id ≈ BiDi context id under the mapper), else fall back to URL + creation order. Cache the mapping; refresh on navigation. Expose `Get BiDi Context For Current Page` for explicit override. *Acknowledged:* this is the main fragility surface, covered by per-browser integration tests.

**D7 — Read/observe split to avoid two-client contention.**
BiDi is used for observation only; mutation/interaction stays with Playwright. Keywords avoid issuing conflicting commands (e.g. both navigating).

**D8 — Phased delivery.** Phase 0 spike (validate parallel BiDi+CDP coexistence — **kill criterion** if they cannot coexist) → Phase 1 plugin skeleton + session/network/log on Chromium → Phase 2 correlation + Firefox + per-browser integration tests → Phase 3 script/realm + `Wait For BiDi ...` + bounded buffers + libdoc/README/example suite + run-on-failure.

## Risks / Trade-offs

- **Parallel BiDi + CDP session cannot coexist on one instance** → Phase 0 spike with explicit kill criterion before any RF integration; fallback to launch-two-browsers or separate-library model.
- **Two clients race/contend on the same targets** → restrict BiDi to read/observe; leave navigation/interaction to Playwright; document the split.
- **Page ↔ context correlation is fragile** → cache + refresh on navigation; per-browser integration tests; manual-override keyword.
- **BiDi spec churn (pre-final command/event shapes)** → thin client localises blast radius; pin tested browser versions; isolate behind an interface.
- **Asyncio loop / unclosed socket on crash (most likely flakiness source)** → robust teardown tied to plugin lifecycle + `Close Browser`; defensive `__del__`/`atexit` safety nets.
- **Browser was not launched BiDi-reachable** → extension cannot function; document the launch/connect contract tightly and provide a launcher keyword.
- **Overlap with CDP on Chromium-only projects** → be explicit that BiDi's differentiator is cross-browser + standards future-proofing (primarily Firefox); a CDP extension is simpler if only Chromium is targeted.

## Migration Plan

Greenfield additive package — no existing behavior changes, no rollback of existing features needed. Deploy as a new `Browser-BiDi` plugin in the mono-repo. Users opt in by adding `plugins=BrowserBiDi.py` to their `Library Browser` import and launching a BiDi-reachable browser. Rollback = remove the plugin import; the host Browser library is unaffected. **Phase 4 upstream alignment:** if/when Playwright exposes a stable public BiDi session, evaluate folding the side-channel into native plumbing and deprecating the parallel connection (the swappable client interface from D3 eases this).

## Validation findings (Phase 0 + integration, 2026-05-29)

Executed against real browsers (see `spike/RESULTS.md`). The premise holds:

- **Chromium: full Strategy 1 confirmed.** A parallel BiDi session coexists with
  Playwright's CDP session on the *same* chromedriver-launched browser. The full Robot
  suite passes 3/3 (correlation, network + response body, console). Kill criterion (1.5)
  not triggered.
- **Response bodies require a data collector.** `network.getData` fails with "No collected
  response data" unless `network.addDataCollector` is registered *before* the response.
  Now wired into `Connect BiDi` (best-effort). Bodies are Chromium-reliable; Firefox
  `getData` fails on compressed streams.
- **`session.new` is redundant on a driver `webSocketUrl`** (already an established
  session) — made best-effort.
- **Firefox cannot do full Strategy 1 via Browser.** No CDP, and Playwright cannot attach
  to an external Firefox (launches its own), so the BiDi and Playwright instances differ.
  Firefox is validated at the BiDi-client level only (`spike/run_firefox.py`, 6/6),
  confirming the proposal's "browser coverage is uneven" caveat. This is the main scope
  correction from implementation.
- **Launcher hardening:** wait for driver readiness before `POST /session`; clean up the
  driver on handshake failure; DELETE the session on close so geckodriver quits Firefox.

## Open Questions

- Exact BiDi endpoint negotiation per launcher: Chromedriver/Geckodriver `webSocketUrl` vs. Chromium `/session` negotiation vs. the CDP mapper — which to default to per browser?
- Should the launcher helper be a keyword, a separate CLI, or documentation only?
- Buffer default size `N` and overflow policy (drop-oldest vs. error) — needs tuning against real runs.
- Whether `BiDi Add Preload Script` realm targeting is needed in Phase 3 or can be deferred.
- Minimum supported `Browser`/Playwright and browser versions to pin for correlation stability.
