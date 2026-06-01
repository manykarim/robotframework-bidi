## Context

The `browser-bidi-extension` change shipped and was archived; its specs were synced to `openspec/specs/`. Subsequent work added keywords that the specs do not yet describe: `Launch BiDi Browser`, `Close BiDi Browser`, `Clear BiDi Buffers`, `Get BiDi Contexts`, and the `transport` argument on `Connect BiDi`. All are implemented, validated by unit tests and `examples/self_launching.robot`, and driverless on both Chrome (chromium-bidi mapper) and Firefox (native). This change brings the specs back in line; no behaviour changes.

## Goals / Non-Goals

**Goals:**
- Describe the launch keywords, transport selection, buffer clearing, and context enumeration as normative requirements matching shipped behaviour.

**Non-Goals:**
- No code changes, no new dependencies, no new capabilities. Re-implementing or extending the mapper/driverless support is out of scope (already done in the archived change).

## Decisions

**D1 — Launch as a keyword pair, not just a helper.** The original spec only required a launcher *helper* (`SHOULD`). The shipped API is two keywords (`Launch BiDi Browser` returning endpoints, `Close BiDi Browser`), so the requirement is upgraded to mandate them. *Alternative:* a single launch-and-connect keyword (rejected — keeps launch and connect decoupled and flexible).

**D2 — Tracked teardown.** The launched browser is owned by the plugin and torn down on `Close BiDi Browser`, `Disconnect BiDi`, and `atexit`. Browsers the user launched themselves are untouched (the plugin only closes what it started). This prevents orphans without surprising users who manage their own browser.

**D3 — Transport selection on `Connect BiDi`.** A `transport` argument (`websocket` default, `cdp-mapper` for driverless Chrome) selects the BiDi client. This is recorded on the existing "Establish a side-channel BiDi session" requirement rather than as a new capability, since it is part of connecting.

**D4 — `Get BiDi Contexts` lives in page-correlation.** Enumerating the browsing-context tree is the mechanism users employ to target an iframe's context for the element getters, so it belongs with correlation.

**D5 — `Clear BiDi Buffers` in session-management.** Buffer lifecycle is already covered by the "Background event loop with bounded buffers" requirement; clearing is a sibling concern, added there.

## Risks / Trade-offs

- [Spec drifts from a stricter `MUST` than older Browser/Playwright behaviour] → requirements are phrased to match the validated implementation; no new guarantees beyond what tests cover.
- [`Disconnect BiDi` closing a launched browser surprises a user expecting reconnect] → scoped strictly to browsers the plugin launched; externally provided browsers are never closed. Documented in the keyword.

## Migration Plan

Additive spec edits only. On archive, sync updates the two main specs. Rollback = revert the spec edits; no runtime impact.

## Open Questions

- Whether to later add a single `Launch And Connect BiDi` convenience keyword (deferred; out of scope here).
