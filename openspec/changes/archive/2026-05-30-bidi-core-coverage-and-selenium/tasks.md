## 1. Phase 1 — Extract the library-agnostic core

- [x] 1.1 Create `bidi_core` package; move client, `mapper_client`, commands, buffers, serialization, loop_runner, correlation (no Browser/Playwright imports)
- [x] 1.2 Define the host adapter contract (`current_page_ref()` for correlation; optional launch helpers)
- [x] 1.3 Refactor `Browser_BiDi` into a thin adapter over `bidi_core`; re-export existing names so imports/keywords are unchanged
- [x] 1.4 Move/retarget unit tests to `bidi_core`; confirm full suite + existing example suites pass (no behaviour change)

## 2. Phase 2 — Network interception & timing (priority 1)

- [x] 2.1 Add command wrappers: `network.addIntercept`/`removeIntercept`, `continueRequest`/`continueResponse`/`provideResponse`/`failRequest`/`continueWithAuth`, `setExtraHeaders`/`setCacheBehavior`
- [x] 2.2 Implement the intercept lifecycle: register declarative actions, auto-answer matching paused requests on the loop, timeout + auto-continue fallback with warning
- [x] 2.3 Keywords: mock response, fail request, continue-with-auth, set extra headers, set cache behavior
- [x] 2.4 FetchTimingInfo getter/assertion (DNS/connect/TLS/TTFB) with threshold assertions
- [x] 2.5 Unit tests (fake client) + live validation per engine (mock, fault, auth, TTFB)

## 3. Phase 3 — Emulation, user contexts

- [x] 3.1 Emulation keywords: geolocation, locale, timezone, user-agent, forced-colors, network-conditions (throttle/offline), viewport, screen/orientation/scrollbar/touch, scripting-enabled
- [x] 3.2 User-context keywords: `New BiDi Context` / `Remove BiDi Context` (createUserContext/removeUserContext); track + auto-remove on teardown
- [x] 3.3 Unit tests + live validation (offline, locale/timezone formatting, forced-colors, two-context cookie isolation)

## 4. Phase 4 — Input/uploads, storage writes, navigation/downloads

- [x] 4.1 `input.performActions` (pointer/key/wheel) + `setFiles` + `fileDialogOpened`
- [x] 4.2 `storage.setCookie`/`deleteCookies` with `PartitionKey`; auth-cookie seeding
- [x] 4.3 Navigation-event capture (navigationStarted/domContentLoaded/load/navigationFailed/fragmentNavigated/historyUpdated) + wait keywords
- [x] 4.4 Downloads: `setDownloadBehavior` + `downloadWillBegin`/`downloadEnd` wait/read
- [x] 4.5 Unit + live validation (drag-drop, hidden-input upload, cookie seed/delete, SPA route, download)

## 5. Phase 5 — SeleniumLibrary adapter

- [x] 5.1 Create the `Selenium_BiDi` adapter implementing the core's adapter contract via the Selenium driver
- [x] 5.2 Connect BiDi to the Selenium-driven browser (Firefox native; Chrome via mapper over the driver endpoint)
- [x] 5.3 Expose portable keywords (network observe/mock, log, user contexts, emulation, preload) with names parallel to the Browser adapter
- [x] 5.4 Example SeleniumLibrary suite (no-console-errors, mock endpoint, isolated contexts) + live validation

## 6. Phase 6 — Capability gating & support matrix

- [x] 6.1 Author the per-engine/version support matrix (ship as data) pinned to a tested BiDi spec revision
- [x] 6.2 Gate each control-side keyword; fail fast with an actionable "unsupported on this engine" message
- [x] 6.3 Tests for gating (supported → runs; unsupported → clear failure)

## 7. Phase 7 — Packaging & init installer

- [x] 7.1 Restructure as a pip distribution: `bidi_core` core + `[browser]` / `[selenium]` extras; mapper as package data
- [x] 7.2 Console-script `init`: refresh/align the mapper to local Chrome; optional opt-in driver/browser fetch with checksum verification; never auto-run on import
- [x] 7.3 Docs/README + per-host quickstarts; build the wheel and verify both extras install independently
- [x] 7.4 Update libdoc for both adapters; smoke-test install in a clean environment
