## ADDED Requirements

### Requirement: Library-agnostic BiDi core
The extension SHALL provide a `bidi_core` engine — BiDi client (WebSocket and chromium-bidi mapper transports), command modules, bounded buffers, serialization, and the background loop — that depends only on a WebSocket library and does NOT import any host test library (Browser/Playwright or Selenium).

#### Scenario: Core imports without a host library
- **WHEN** `bidi_core` is imported in an environment without Browser or Selenium installed
- **THEN** the import succeeds and the client, buffers, and serialization are usable

#### Scenario: Existing Browser keywords keep working
- **WHEN** the Browser plugin is used after the core extraction
- **THEN** all existing Browser-BiDi keywords behave exactly as before (the plugin is a thin adapter re-exporting the core)

### Requirement: Host adapter contract
The core SHALL define an adapter contract exposing the two host-specific concerns: resolving the host's current page to correlation hints (target id and/or URL), and optionally launching a BiDi-reachable browser. A host adapter SHALL implement this contract so the same core can back multiple test libraries.

#### Scenario: Correlation via the adapter
- **WHEN** a page-scoped keyword runs through any adapter
- **THEN** the core obtains the current page's correlation hints from that adapter and resolves the BiDi context without host-specific code in the core

#### Scenario: Two adapters share one core
- **WHEN** both the Browser adapter and the SeleniumLibrary adapter are installed
- **THEN** they reuse the same `bidi_core` engine and command modules rather than duplicating BiDi logic
