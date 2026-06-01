## Why

`docs/research/webdriver-bidi-testing-analysis.md` reaches two conclusions. First, the highest-value BiDi capabilities for testing are the **control/interception** modules the extension does not yet cover — `network` mocking/fault-injection/auth, `emulation` overrides, isolated `browser` user contexts, `input` actions/uploads, `storage` writes, and navigation/download events. Second, the biggest ecosystem opportunity is **SeleniumLibrary**, which today has no native equivalent for most of this and relies on Chromium-locked CDP hacks or external proxies.

Today our BiDi logic is welded to the Browser library plugin. To serve both Browser and Selenium users without duplicating logic — and to ship it cleanly — we should extract a **library-agnostic BiDi core**, expand object coverage to the control side, add a **SeleniumLibrary** keyword layer over the same core, and distribute it as a **pip package with a custom `init` installer** that provisions the chromium-bidi mapper and (optionally) drivers/browsers, following SeleniumLibrary's documented extension model.

## What Changes

- **Extract a framework-agnostic BiDi core** (`bidi_core`): the client (websocket + cdp-mapper), command modules, buffers, serialization, loop runner, and a small **adapter contract** for the two host-specific concerns (page↔context correlation, browser launch). The existing Browser plugin becomes a thin adapter over this core; **no change to existing keyword behaviour**.
- **Add `network` interception & mocking**: `addIntercept` + `continueRequest`/`continueResponse`/`provideResponse`/`failRequest`/`continueWithAuth`, plus `setExtraHeaders`/`setCacheBehavior`, and FetchTimingInfo-based **performance assertions** (e.g. TTFB threshold).
- **Add `emulation` overrides**: geolocation, locale, timezone, forced-colors, network-conditions (throttle/offline), user-agent, scripting-enabled, screen/orientation/scrollbar/touch, and viewport.
- **Add `browser` user contexts**: `createUserContext`/`removeUserContext` for fast, hermetic, isolated parallelism (cookies/storage/cache separation).
- **Add `input` actions & uploads**: `performActions` (pointer/key/wheel) and `setFiles`, plus the `fileDialogOpened` event.
- **Add `storage` writes**: `setCookie`/`deleteCookies` with `PartitionKey`, complementing the existing read-only `Get BiDi Cookies`.
- **Add navigation & download events**: navigation lifecycle (`navigationStarted`/`domContentLoaded`/`load`/`navigationFailed`/`fragmentNavigated`/`historyUpdated`) and `downloadWillBegin`/`downloadEnd` with `setDownloadBehavior`.
- **Add a SeleniumLibrary BiDi layer**: a thin keyword adapter over the core targeting SeleniumLibrary suites, with keyword names kept recognizably close to the Browser-side keywords so suites stay portable.
- **Distribute as an installable package**: a pip distribution with a custom CLI **`init`** step that vendors/refreshes the chromium-bidi mapper and optionally fetches matching drivers/browsers; capability **gating** per browser/version with clear "unsupported on this engine" errors.

## Capabilities

### New Capabilities
- `bidi-shared-core`: Library-agnostic BiDi engine plus the adapter contract (correlation + launch) that lets the same core back both Browser and SeleniumLibrary.
- `bidi-network-interception`: Request/response intercept, mock, fault injection, auth handling, extra headers / cache behaviour, and FetchTimingInfo performance assertions.
- `bidi-emulation`: Environment overrides — geolocation, locale, timezone, forced-colors, network conditions, user-agent, scripting-enabled, screen/orientation/scrollbar/touch, and viewport.
- `bidi-user-contexts`: Create/remove isolated user contexts for hermetic, parallel test isolation.
- `bidi-interaction-and-uploads`: `input.performActions` gestures and `setFiles` uploads, including native file-dialog detection.
- `bidi-storage-management`: Cookie writes/deletes with partition awareness, complementing existing cookie reads.
- `bidi-navigation-and-downloads`: Navigation-lifecycle event capture (incl. SPA route changes) and managed download handling.
- `selenium-bidi-layer`: A SeleniumLibrary keyword adapter over the shared core with portable keyword naming.
- `bidi-distribution-installer`: Pip-installable packaging with a custom `init` installer and per-engine capability gating.

### Modified Capabilities
<!-- None at the requirement level: the core extraction is an internal refactor that preserves existing keyword behaviour. New behaviour is captured as the new capabilities above. -->

## Impact

- **New package layout**: a `bidi_core` package (framework-neutral) with `Browser_BiDi` and a new `Selenium_BiDi` (or similar) as thin adapters; a console-script `init` entry point.
- **Dependencies**: adds `selenium>=4.x` as an optional extra for the Selenium layer; keeps `websockets`; `robotframework-browser` stays optional (Browser adapter only).
- **Spec maturity risk**: the analysis is against a W3C **Editor's Draft**; sandbox realms and parts of `emulation` carry open issues, and Chromium/Firefox support differs per command — every new keyword is **capability-gated** with a documented support matrix and fail-fast errors.
- **Backwards compatibility**: existing Browser-BiDi keywords and imports are preserved (re-exported from the new core); driverless launch and the vendored mapper continue to work.
- **Testing**: unit tests move with the core (no browser needed); live validation per engine for the new control-side modules, which are inherently browser-version-sensitive.
