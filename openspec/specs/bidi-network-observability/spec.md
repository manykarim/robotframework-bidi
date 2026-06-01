# bidi-network-observability Specification

## Purpose
TBD: created by syncing change 'browser-bidi-extension'. Update Purpose to describe this capability.

## Requirements

### Requirement: Capture network events
The extension SHALL capture BiDi network events (`beforeRequestSent`, `responseStarted`, `responseCompleted`, `fetchError`) for subscribed contexts and expose them via a `Get BiDi Network Events` keyword that returns a list of plain JSON-serialisable dicts. The keyword SHALL support optional filtering by URL glob and by a `since` marker.

#### Scenario: Retrieve completed responses
- **WHEN** a page has loaded resources and the user calls `Get BiDi Network Events`
- **THEN** the keyword returns structured events including request/response metadata such as timings, sizes, and cache state

#### Scenario: Filter by URL glob
- **WHEN** a user calls `Get BiDi Network Events` with `url_glob=**/api/**`
- **THEN** only events whose URL matches the glob are returned

### Requirement: Retrieve response bodies
The extension SHALL provide a `Get BiDi Response Body` keyword that retrieves the body of a completed response by its request id via the BiDi network module, returning the body as text or bytes. This SHALL work reliably post-load without requiring the caller to intercept before the response.

#### Scenario: Retrieve a body after load
- **WHEN** a user calls `Get BiDi Response Body` with the request id from a captured `responseCompleted` event
- **THEN** the keyword returns the response body content

#### Scenario: Unknown request id
- **WHEN** a user calls `Get BiDi Response Body` with a request id that has no retrievable body
- **THEN** the keyword fails with a clear error rather than returning an empty or misleading value

### Requirement: Wait for a matching response
The extension SHALL provide a `Wait For BiDi Response` keyword that blocks until a network response matching a URL glob is observed (within an optional timeout) and returns the matching event.

#### Scenario: Wait succeeds
- **WHEN** a user calls `Wait For BiDi Response` with `**/api/profile` and a matching response arrives within the timeout
- **THEN** the keyword returns the matching response event

#### Scenario: Wait times out
- **WHEN** no matching response arrives within the timeout
- **THEN** the keyword fails with a timeout error
