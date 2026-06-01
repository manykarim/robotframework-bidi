# bidi-page-correlation Specification

## Purpose
TBD: created by syncing change 'browser-bidi-extension'. Update Purpose to describe this capability.

## Requirements

### Requirement: Correlate Playwright pages to BiDi browsing contexts
The extension SHALL map the host library's active Playwright page to the corresponding BiDi `browsingContext` id. It SHALL read the page's CDP target id and URL via a bundled `jsextension` helper (loaded through `initialize_js_extension`) and match against `browsingContext.getTree`, preferring target-id matching and falling back to URL plus creation order.

#### Scenario: Match by target id
- **WHEN** the transport exposes a target id that aligns with a BiDi context id (e.g. Chromium under the mapper)
- **THEN** the extension maps the current page to that BiDi context id by target id

#### Scenario: Fallback when target id is unavailable
- **WHEN** target-id alignment is not available
- **THEN** the extension falls back to matching by page URL and context creation order to determine the BiDi context id

### Requirement: Cache and refresh the page-context mapping
The extension SHALL cache the page ↔ context mapping and refresh it on navigation so that observability keywords target the correct context after a page navigates.

#### Scenario: Mapping refreshed after navigation
- **WHEN** the current page navigates to a new URL
- **THEN** the extension refreshes the cached mapping so subsequent BiDi keywords resolve to the correct, current context

### Requirement: Expose the resolved context to users
The extension SHALL provide a `Get BiDi Context For Current Page` keyword that returns the resolved BiDi context id, and SHALL allow advanced users to pass an explicit context id to observability keywords to override automatic correlation.

#### Scenario: Retrieve current context id
- **WHEN** a user calls `Get BiDi Context For Current Page` after `Connect BiDi`
- **THEN** the keyword returns the BiDi context id corresponding to the host library's active page

#### Scenario: Manual override
- **WHEN** a user passes an explicit BiDi context id to an observability keyword
- **THEN** the extension uses that id directly instead of automatic correlation

### Requirement: Enumerate browsing contexts
The extension SHALL provide a `Get BiDi Contexts` keyword that returns the flattened browsing-context tree — top-level pages and nested iframes — each entry exposing at least its context id and URL, so users can target a specific iframe's context for the element getters.

#### Scenario: List page and iframe contexts
- **WHEN** the current page contains an iframe and the user calls `Get BiDi Contexts`
- **THEN** the returned list includes both the top-level page context and the iframe's context, each with its context id and URL

#### Scenario: Target an iframe by its context
- **WHEN** a user selects the iframe's context id from `Get BiDi Contexts` and passes it to an element getter
- **THEN** the getter resolves nodes within that iframe
