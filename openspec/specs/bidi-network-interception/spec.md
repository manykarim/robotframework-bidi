# bidi-network-interception Specification

## Purpose
TBD: created by syncing change 'bidi-core-coverage-and-selenium'. Update Purpose to describe this capability.

## Requirements

### Requirement: Intercept and mock network requests
The extension SHALL register network intercepts (`network.addIntercept`) matching by URL pattern (and optionally method) and answer each paused request with a declarative action: provide a mock response (status, headers, body), fail the request, or continue it unchanged. Paused requests SHALL be answered on the background loop so Robot keywords remain synchronous.

#### Scenario: Mock an endpoint
- **WHEN** a user registers a mock for `*://*/api/profile` returning status 200 and a JSON body, then the page requests that URL
- **THEN** the page receives the mocked response and the real server is not contacted

#### Scenario: Inject a fault
- **WHEN** a user registers a fault for an endpoint and the page requests it
- **THEN** the request fails as configured (e.g. `failRequest`), exercising the page's error handling

#### Scenario: Unanswered request does not hang the suite
- **WHEN** a paused request matches no explicit action within a timeout
- **THEN** the extension auto-continues it and logs a warning rather than blocking indefinitely

### Requirement: Authentication and header control
The extension SHALL handle `network.authRequired` via `continueWithAuth` (supply or cancel credentials), and SHALL support `setExtraHeaders` and `setCacheBehavior` for header injection and caching-correctness tests.

#### Scenario: Answer a basic-auth challenge
- **WHEN** a protected resource triggers `authRequired` and credentials are configured
- **THEN** the extension supplies them via `continueWithAuth` and the resource loads

### Requirement: Performance timing assertions
The extension SHALL expose FetchTimingInfo-derived timings (DNS, connect, TLS, TTFB) for captured responses as a getter with optional assertion, so tests can assert thresholds such as time-to-first-byte.

#### Scenario: Assert a TTFB threshold
- **WHEN** a user asserts the TTFB of a captured API response is under a threshold
- **THEN** the assertion passes for a fast response and fails with a clear message for a slow one
