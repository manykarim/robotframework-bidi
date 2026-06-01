## ADDED Requirements

### Requirement: Establish a side-channel BiDi session
The extension SHALL open an independent WebDriver BiDi WebSocket connection to the same browser instance that the host Browser library is driving, without routing through Playwright or the gRPC bridge. A `Connect BiDi` keyword SHALL accept the BiDi WebSocket URL and an optional browser hint, run the BiDi `session.new` handshake, and make the session available to subsequent keywords.

#### Scenario: Connect to a BiDi-reachable browser
- **WHEN** a user calls `Connect BiDi` with a valid `ws://` URL for a browser launched with BiDi reachable
- **THEN** the extension opens the WebSocket, completes `session.new`, and reports a connected session ready for subscriptions

#### Scenario: Browser not reachable over BiDi
- **WHEN** a user calls `Connect BiDi` against a URL where no BiDi endpoint is listening
- **THEN** the keyword SHALL fail with a clear, actionable error explaining the browser must be launched with BiDi reachable

#### Scenario: Reject WebKit/Safari
- **WHEN** the target browser is WebKit/Safari
- **THEN** the extension SHALL degrade gracefully and report that BiDi is unsupported for that browser rather than hanging

### Requirement: Tear down the BiDi session
The extension SHALL close the BiDi session, unsubscribe from all events, stop the background event loop, and release the WebSocket on `Disconnect BiDi` and best-effort on host `Close Browser` / library shutdown. Teardown SHALL be defensive against crashes (e.g. `atexit`/`__del__` safety nets) so no orphaned loops or unclosed sockets remain.

#### Scenario: Explicit disconnect
- **WHEN** a user calls `Disconnect BiDi`
- **THEN** the extension unsubscribes all events, closes the WebSocket, stops the background loop, and is left in a state where `Connect BiDi` can be called again

#### Scenario: Auto-teardown on browser close
- **WHEN** the host Browser library closes the browser without an explicit `Disconnect BiDi`
- **THEN** the extension SHALL best-effort tear down the BiDi session so no orphaned asyncio loop or open socket survives the run

### Requirement: Subscribe and unsubscribe to event classes
The extension SHALL expose `BiDi Subscribe` and `BiDi Unsubscribe` keywords that call BiDi `session.subscribe`/`session.unsubscribe` for one or more event types (e.g. `network.responseCompleted`, `log.entryAdded`) effective for the whole run. An optional `auto_subscribe` argument on `Connect BiDi` SHALL allow subscribing at connect time.

#### Scenario: Subscribe to multiple event types
- **WHEN** a user calls `BiDi Subscribe` with `events=network.responseCompleted, log.entryAdded`
- **THEN** the extension issues `session.subscribe` for those types and begins buffering matching events

#### Scenario: Unsubscribe stops buffering
- **WHEN** a user calls `BiDi Unsubscribe` for a previously subscribed event type
- **THEN** the extension issues `session.unsubscribe` and stops adding new events of that type to its buffers

### Requirement: Background event loop with bounded buffers
The extension SHALL run its BiDi client on a dedicated asyncio loop on a background thread owned by the plugin instance, dispatching incoming events into per-event-class bounded buffers (configurable maximum size). Synchronous Robot keywords SHALL push work onto that loop and block for the result without blocking Robot's main thread.

#### Scenario: Events captured across keyword calls
- **WHEN** events arrive between two separate keyword calls after a subscription is active
- **THEN** the events are buffered on the background loop and remain retrievable by a later keyword

#### Scenario: Buffer overflow drops oldest
- **WHEN** the number of buffered events for a class exceeds the configured maximum
- **THEN** the oldest events are dropped (bounded memory) and the overflow is observable rather than silently unbounded

### Requirement: Assist launching a BiDi-reachable browser
The extension SHALL document the launch/connect contract (a browser exposing both a CDP debugging endpoint and a reachable BiDi endpoint) and SHOULD provide a launcher helper to start such a browser for Chromium and Firefox.

#### Scenario: Launch helper produces a connectable endpoint
- **WHEN** a user invokes the provided launcher helper for a supported browser
- **THEN** a browser is started exposing both a CDP endpoint usable by `Connect To Browser ... use_cdp=True` and a BiDi endpoint usable by `Connect BiDi`
