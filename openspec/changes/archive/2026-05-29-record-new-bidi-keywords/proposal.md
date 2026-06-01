## Why

Four keywords were added after the `browser-bidi-extension` change was archived (and two more during its example work), so the synced specs in `openspec/specs/` do not describe them. The specs should match the shipped, validated behaviour: the extension can now launch its own driverless browser, clear its buffers, enumerate browsing contexts, and select a BiDi transport. This is a documentation/spec-sync change — the code already exists and is tested.

## What Changes

- Record **`Launch BiDi Browser`** / **`Close BiDi Browser`**: launch a BiDi-reachable browser as a keyword (driverless by default — Chrome via the bundled chromium-bidi mapper, Firefox native — no chromedriver/geckodriver), returning `{bidi_url, cdp_url, transport, browser}`; the launched browser is tracked and torn down on `Close BiDi Browser`, `Disconnect BiDi`, and process exit.
- Record the **`transport`** argument on `Connect BiDi` (`websocket` | `cdp-mapper`) enabling driverless Chrome via the mapper.
- Record **`Clear BiDi Buffers`**: drop buffered network/log events (e.g. for clean per-test counts).
- Record **`Get BiDi Contexts`**: return the flattened browsing-context tree (top-level pages and nested iframes) for targeting an iframe's context.
- No code changes are required; this aligns the specs with implemented behaviour.

## Capabilities

### New Capabilities
<!-- None — all changes refine existing capabilities. -->

### Modified Capabilities
- `bidi-session-management`: the launch helper becomes a first-class keyword pair with driverless transports and tracked teardown; `Connect BiDi` gains a `transport` option; a new buffer-clearing keyword is added.
- `bidi-page-correlation`: add enumeration of the browsing-context tree for explicit iframe/context targeting.

## Impact

- Specs only: `openspec/specs/bidi-session-management/spec.md` and `openspec/specs/bidi-page-correlation/spec.md` (via delta specs in this change).
- Affected code already shipped: `Browser_BiDi/BrowserBiDi.py` (keywords), `Browser_BiDi/launcher.py`, `Browser_BiDi/mapper_client.py`; covered by unit tests and `examples/self_launching.robot`.
- No new dependencies; no breaking changes.
