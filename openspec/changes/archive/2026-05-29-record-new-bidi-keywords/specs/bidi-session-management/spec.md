## MODIFIED Requirements

### Requirement: Establish a side-channel BiDi session
The extension SHALL open an independent WebDriver BiDi connection to the same browser instance that the host Browser library is driving, without routing through Playwright or the gRPC bridge. A `Connect BiDi` keyword SHALL accept the BiDi endpoint URL, an optional browser hint, and an optional `transport`, run the BiDi `session.new` handshake, and make the session available to subsequent keywords. The `transport` argument SHALL select how BiDi is spoken: `websocket` (default) connects directly to a BiDi WebSocket (Firefox native, or a driver-provided `webSocketUrl`); `cdp-mapper` connects to Chrome's CDP `webSocketDebuggerUrl` and speaks BiDi through the bundled chromium-bidi mapper.

#### Scenario: Connect to a BiDi-reachable browser
- **WHEN** a user calls `Connect BiDi` with a valid `ws://` URL for a browser launched with BiDi reachable
- **THEN** the extension opens the connection, completes `session.new`, and reports a connected session ready for subscriptions

#### Scenario: Connect to driverless Chrome via the mapper
- **WHEN** a user calls `Connect BiDi` with Chrome's CDP `webSocketDebuggerUrl` and `transport=cdp-mapper`
- **THEN** the extension loads the chromium-bidi mapper and exposes a working BiDi session without chromedriver

#### Scenario: Browser not reachable over BiDi
- **WHEN** a user calls `Connect BiDi` against a URL where no BiDi endpoint is listening
- **THEN** the keyword SHALL fail with a clear, actionable error explaining the browser must be launched with BiDi reachable

#### Scenario: Reject WebKit/Safari
- **WHEN** the target browser is WebKit/Safari
- **THEN** the extension SHALL degrade gracefully and report that BiDi is unsupported for that browser rather than hanging

### Requirement: Assist launching a BiDi-reachable browser
The extension SHALL provide a `Launch BiDi Browser` keyword that starts a BiDi-reachable browser and returns its endpoints (`bidi_url`, `cdp_url`, `transport`, `browser`), and a `Close BiDi Browser` keyword that stops it. Launching SHALL be **driverless by default** — Chromium via the bundled chromium-bidi mapper and Firefox via its native BiDi endpoint, requiring no chromedriver/geckodriver. A browser started by `Launch BiDi Browser` SHALL be tracked and torn down on `Close BiDi Browser`, on `Disconnect BiDi`, and via the process-exit safety net; browsers the user launched themselves SHALL NOT be closed by the extension.

#### Scenario: Launch returns connectable endpoints
- **WHEN** a user calls `Launch BiDi Browser    chromium`
- **THEN** a driverless browser starts and the keyword returns a `cdp_url` usable by `Connect To Browser ... use_cdp=True` and a `bidi_url` + `transport` usable by `Connect BiDi`

#### Scenario: Launch Firefox driverless
- **WHEN** a user calls `Launch BiDi Browser    firefox`
- **THEN** Firefox starts exposing native BiDi (no geckodriver) and the returned `transport` is `websocket`

#### Scenario: Launched browser is torn down
- **WHEN** a launched browser exists and the user calls `Close BiDi Browser` (or `Disconnect BiDi`, or the process exits)
- **THEN** that browser is closed with no orphaned process, while any externally launched browser is left untouched

## ADDED Requirements

### Requirement: Clear buffered events
The extension SHALL provide a `Clear BiDi Buffers` keyword that drops all buffered network and log events, so callers can obtain clean counts between scenarios without reconnecting.

#### Scenario: Buffers cleared between tests
- **WHEN** events have been buffered and the user calls `Clear BiDi Buffers`
- **THEN** subsequent count/list getters report only events captured after the clear
