# bidi-navigation-and-downloads Specification

## Purpose
TBD: created by syncing change 'bidi-core-coverage-and-selenium'. Update Purpose to describe this capability.

## Requirements

### Requirement: Navigation lifecycle events
The extension SHALL capture BiDi `browsingContext` navigation events (`navigationStarted`, `domContentLoaded`, `load`, `navigationFailed`, `fragmentNavigated`, `historyUpdated`) and expose keywords to wait for and read them, including detecting SPA route changes that classic waits miss.

#### Scenario: Wait for load milestone
- **WHEN** a user waits for the `load` event after triggering navigation
- **THEN** the keyword returns once the page has loaded, with the event's timing

#### Scenario: Detect an SPA route change
- **WHEN** the application performs a history/fragment navigation without a full page load
- **THEN** the extension reports the route change via `historyUpdated`/`fragmentNavigated`

### Requirement: Managed downloads
The extension SHALL handle downloads via `browser.setDownloadBehavior` and the `downloadWillBegin`/`downloadEnd` events, exposing keywords to configure the download location and wait for a download to complete.

#### Scenario: Wait for a download to finish
- **WHEN** a user configures downloads and triggers one, then waits for completion
- **THEN** the extension reports the completed download (path/filename) once `downloadEnd` fires
