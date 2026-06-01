# bidi-log-observability Specification

## Purpose
TBD: created by syncing change 'browser-bidi-extension'. Update Purpose to describe this capability.

## Requirements

### Requirement: Capture console log entries
The extension SHALL capture raw BiDi `log.entryAdded` events for subscribed contexts and expose them via a `Get BiDi Console Log` keyword returning plain JSON-serialisable dicts that preserve level, arguments, source, timestamp, and originating realm. The keyword SHALL support optional filtering by level and by a `since` marker.

#### Scenario: Retrieve console entries
- **WHEN** page scripts emit console messages and the user calls `Get BiDi Console Log`
- **THEN** the keyword returns structured entries including level, message args, source location, timestamp, and realm

#### Scenario: Filter by level
- **WHEN** a user calls `Get BiDi Console Log` with `level=error`
- **THEN** only entries at the requested level are returned

### Requirement: Capture uncaught JS exceptions
The extension SHALL surface uncaught JavaScript exceptions as structured entries including a full stack trace and source location, exposed via a `Get BiDi JS Errors` keyword.

#### Scenario: Retrieve structured exceptions
- **WHEN** the page throws an uncaught exception and the user calls `Get BiDi JS Errors`
- **THEN** the keyword returns a structured entry with the exception message, stack trace, and source location

#### Scenario: No errors yields empty list
- **WHEN** no uncaught exceptions have occurred and the user calls `Get BiDi JS Errors`
- **THEN** the keyword returns an empty list

### Requirement: Wait for a matching log entry
The extension SHALL provide a `Wait For BiDi Log Entry` keyword that blocks until a log entry matching a caller-supplied matcher is observed within an optional timeout, returning the matching entry.

#### Scenario: Wait succeeds
- **WHEN** a user calls `Wait For BiDi Log Entry` with a matcher and a matching entry arrives within the timeout
- **THEN** the keyword returns the matching log entry

#### Scenario: Wait times out
- **WHEN** no matching entry arrives within the timeout
- **THEN** the keyword fails with a timeout error
