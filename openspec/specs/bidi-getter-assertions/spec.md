# bidi-getter-assertions Specification

## Purpose
TBD: created by syncing change 'browser-bidi-extension'. Update Purpose to describe this capability.

## Requirements

### Requirement: Getter keywords with inline assertions
The extension SHALL expose getter keywords that follow the Robot Framework
Browser library pattern using `robotframework-assertionengine`: each returns the
retrieved value and, when an `assertion_operator` and `assertion_expected` are
supplied, asserts in the same call (get-and-assert). Optional filter arguments
SHALL be keyword-only so the assertion operator is the natural positional
argument.

#### Scenario: Getter returns value when no operator given
- **WHEN** a getter keyword is called without an assertion operator
- **THEN** it returns the retrieved value unchanged

#### Scenario: Getter asserts when operator given
- **WHEN** a getter is called with an operator and expected value (e.g. `== 200`)
- **THEN** it verifies the value with that operator and fails with a clear message on mismatch

### Requirement: QA-relevant BiDi getters
The extension SHALL provide getter/assertion keywords for the QA-relevant data
retrievable via BiDi: response status, response headers, response body, network
event count, per-resource timings, console log (and count), JS errors (and
count), page URL, page title, DOM snapshot, cookies, located elements (and
count and text), and Web Vitals (TTFB/DCL/load/FCP/LCP). It SHALL also provide a
screenshot capture keyword.

#### Scenario: Assert response status
- **WHEN** a response matching a URL glob has been captured and the user calls the response-status getter with `== 200`
- **THEN** the assertion passes for a 200 response

#### Scenario: Retrieve resource timings
- **WHEN** the user requests resource timings for a captured response
- **THEN** the keyword returns per-resource phase durations (dns/connect/tls/ttfb/download/total) in milliseconds

### Requirement: Page-scoped getters target the correlated page
Getters that read page/DOM state SHALL target the BiDi context correlated to the
host library's active page (not an arbitrary or initial context).

#### Scenario: Title reflects the active page
- **WHEN** the host library has navigated its active page and the user calls the title getter
- **THEN** the returned title is that of the active page, not a blank/initial context

### Requirement: Shadow DOM and iframe retrieval
Element locators SHALL NOT cross shadow boundaries by default. The element count
and text getters SHALL support a `pierce_shadow` option (CSS only) that recurses
into open shadow roots. Iframe content SHALL be retrievable by targeting the
iframe's separate browsing context.

#### Scenario: Read open shadow DOM
- **WHEN** a node exists only inside an open shadow root and the user calls the element-count getter with `pierce_shadow=True`
- **THEN** the node is counted, whereas the default (non-piercing) count does not include it

#### Scenario: Read iframe content via its context
- **WHEN** the user passes an iframe's browsing-context id to an element getter
- **THEN** nodes within that iframe are returned

### Requirement: Driverless BiDi where supported
The launcher SHALL obtain a BiDi endpoint without a WebDriver binary where the
browser supports it. Firefox SHALL be launched driverless (native BiDi via
`--remote-debugging-port`). Chrome, whose debugging port exposes CDP rather than
BiDi, MAY require the chromium-bidi mapper (e.g. via chromedriver).

#### Scenario: Firefox launched without geckodriver
- **WHEN** the launcher starts Firefox with BiDi enabled
- **THEN** a usable BiDi endpoint is produced without geckodriver, and closing it leaves no orphaned browser process

#### Scenario: Non-BiDi endpoint fails loudly
- **WHEN** the client connects to a CDP-only endpoint and issues a BiDi command
- **THEN** it raises a clear error rather than silently returning an empty result
