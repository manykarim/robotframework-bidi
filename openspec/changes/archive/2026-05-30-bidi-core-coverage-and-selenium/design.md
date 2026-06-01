## Context

The extension's BiDi logic (client, command modules, buffers, serialization, loop runner, correlation, mapper) currently lives under `Browser_BiDi` and is coupled to the Browser library (`LibraryComponent`, the jsextension correlation helper, Playwright-driven navigation). The research doc (`docs/research/webdriver-bidi-testing-analysis.md`, against the W3C BiDi Editor's Draft, 11 May 2026) argues the next wins are the **control-side** modules (network interception, emulation, user contexts, input, storage writes, navigation/downloads) and that **SeleniumLibrary** is the bigger audience because it lacks native equivalents. We want one core serving both hosts, broader object coverage, and clean distribution. See `proposal.md` for scope.

## Goals / Non-Goals

**Goals:**
- A library-agnostic `bidi_core` reused by both a Browser adapter (existing) and a new SeleniumLibrary adapter, with portable keyword naming.
- High-value control-side coverage: network mock/intercept/auth/timing, emulation, user contexts, input/uploads, storage writes, navigation/downloads.
- Pip distribution with a custom `init` installer; per-engine capability gating with a support matrix.

**Non-Goals:**
- Re-implementing Playwright/Selenium interaction. BiDi remains the observability/control side-channel; hosts still drive primary navigation/interaction.
- Full one-to-one wrapping of every BiDi command; cover the prioritized testing-relevant surface.
- WebKit/Safari (no BiDi) and `webExtension` (niche) — deferred.
- Stabilizing draft-only features (sandbox realms, unstable `emulation`): gate, don't depend.

## Decisions

**D1 — Extract `bidi_core`; hosts are thin adapters.** Move client/`mapper_client`/commands/buffers/serialization/loop_runner/correlation into `bidi_core`, depending only on `websockets`. Define an **adapter contract** with two host-specific hooks: (a) `current_page_ref() -> {target_id?, url?}` for correlation, and (b) optional launch helpers. The Browser plugin implements (a) via the existing jsextension; the Selenium adapter implements it via Selenium's driver (`driver.current_url`, CDP/BiDi target). *Alternatives:* keep logic in `Browser_BiDi` and duplicate for Selenium (rejected — drift); a base class instead of a protocol (rejected — adapters differ too much). Existing `Browser_BiDi` imports are preserved by re-export.

**D2 — Selenium transport: reuse our core over a side-channel, not Selenium's `webdriver.common.bidi`.** Selenium 4.x exposes some BiDi, but coverage is partial and churning. We already have a validated BiDi client (websocket + chromium-bidi mapper) and driverless launch. The Selenium adapter connects our core to the same browser Selenium drives: Firefox via native BiDi, Chrome via the mapper over the driver's CDP/debugger endpoint. *Alternative:* build purely on `selenium`'s BiDi API (rejected for now — less control, version-fragile; revisit when Selenium's surface stabilizes). The adapter is isolated so this can be swapped.

**D3 — Network interception lifecycle is explicit.** `addIntercept` returns an intercept id; the client must answer each paused request via `continueRequest`/`continueResponse`/`provideResponse`/`failRequest`/`continueWithAuth`. We expose keywords to register intercepts with a declarative action (mock body/status/headers, fail, continue-with-auth) and auto-answer the matching `network.beforeRequestSent`/`authRequired` events on the background loop, so Robot keywords stay synchronous. Unanswered paused requests are a hang risk → default timeout + auto-continue fallback with a logged warning.

**D4 — Emulation/user-context scoping.** BiDi overrides and `createUserContext` are scoped by context/user-context. Keywords accept an optional target (context id or user-context id) and default to the correlated current context. User contexts returned by `createUserContext` are tracked and removed on teardown.

**D5 — Capability gating + support matrix.** Each new keyword checks support for the active engine/version before issuing the command and fails fast with an actionable message ("`network.continueWithAuth` unsupported on Chrome <ver>; use Firefox or upgrade"). A static, documented matrix ships with the package and is the single source of truth; gating reads from it. This contains the Editor's-Draft and engine-divergence risk.

**D6 — Packaging & `init` installer.** Ship a pip distribution exposing the core + both adapters as optional extras (`[browser]`, `[selenium]`). A console-script `init` (à la `rfbrowser init`) (a) vendors/refreshes the chromium-bidi mapper bundle aligned to the local Chrome, and (b) optionally fetches matching chromedriver/geckodriver and/or a browser. The mapper is shipped as package data for offline use; `init` only refreshes/aligns. *Alternative:* post-install hook (rejected — fragile across pip/build backends; an explicit CLI is the SeleniumLibrary-recommended pattern).

**D7 — Portable keyword naming.** Keep keyword names recognizably parallel between hosts (e.g. `BiDi Mock Response`, `Wait For BiDi Response`, `BiDi Set Geolocation`, `New BiDi Context`) so suites move between Browser and Selenium with minimal friction, mirroring the research's portability goal.

## Risks / Trade-offs

- [Editor's-Draft churn; sandbox realms & parts of emulation unstable] → capability-gate every keyword; ship network/log/context first (most mature); pin tested spec revision + engine versions in the matrix.
- [Engine divergence — Firefox most complete, Chromium varies] → support matrix + fail-fast; per-engine live tests; document gaps rather than silently degrade.
- [Intercept deadlocks if a paused request is never answered] → timeout + auto-continue fallback, logged; document the explicit answer model.
- [Two hosts driving one browser (Selenium/CDP + BiDi)] → same read/observe split as the Browser adapter; interception is control but scoped and answered promptly.
- [Selenium's own BiDi API diverging from our side-channel] → adapter isolation (D2) lets us switch transports without touching keywords.
- [Installer fetching drivers/browsers — network, security, version skew] → `init` is opt-in per artifact, verifies checksums, and defaults to "mapper only"; never auto-runs on import.

## Migration Plan

Additive and backwards-compatible. Phase 1: extract `bidi_core`, re-export from `Browser_BiDi` (no behaviour change), CI green. Phase 2: control-side modules behind gating (network → log/timing → emulation → contexts → input/storage/nav-downloads). Phase 3: SeleniumLibrary adapter + portable keywords. Phase 4: packaging + `init`. Rollback at any phase = the new capability keywords are independent; the Browser adapter and existing keywords are unaffected.

## Open Questions

- Selenium adapter correlation: use Selenium's CDP endpoint to reach the mapper, or Selenium 4.x BiDi `webSocketUrl`? Decide during Phase 3 against the then-current Selenium release.
- Should `init` fetch browsers (heavy) or only drivers + mapper? Default proposed: drivers + mapper; browsers opt-in.
- Intercept matching DSL: URL glob only, or also method/resourceType/headers? Start with URL glob + method.
- Where do FetchTimingInfo assertions live — extend `bidi-network-observability` or sit in `bidi-network-interception`? Proposed: a timing getter/assertion in the interception capability since both ship together.
- User-context ↔ host-session interplay when the host (Browser/Selenium) owns the default context.
