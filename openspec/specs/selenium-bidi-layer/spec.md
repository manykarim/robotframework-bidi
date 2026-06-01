# selenium-bidi-layer Specification

## Purpose
TBD: created by syncing change 'bidi-core-coverage-and-selenium'. Update Purpose to describe this capability.

## Requirements

### Requirement: SeleniumLibrary BiDi keyword adapter
The extension SHALL provide a SeleniumLibrary-compatible keyword layer over `bidi_core` that connects a BiDi session to the browser SeleniumLibrary is driving, exposing the high-value BiDi capabilities (network observe/mock, log, user contexts, emulation, preload) to SeleniumLibrary suites. It SHALL NOT require the Browser library.

#### Scenario: Use BiDi from a SeleniumLibrary suite
- **WHEN** a SeleniumLibrary suite imports the BiDi layer and connects after opening a browser
- **THEN** BiDi keywords (e.g. subscribe to logs, mock a response) work against the Selenium-driven browser without the Browser library installed

#### Scenario: No native equivalent regression
- **WHEN** a SeleniumLibrary suite asserts no console errors during a journey via the BiDi log keyword
- **THEN** it captures errors cross-browser in real time, which SeleniumLibrary cannot do natively

### Requirement: Self-contained browser launch
The SeleniumLibrary adapter SHALL provide an `Open BiDi Browser` keyword that opens a BiDi-enabled browser, registers it with SeleniumLibrary (so the normal SeleniumLibrary keywords operate on it), and connects the BiDi session — without requiring any additional helper library or Python file in the test ware.

#### Scenario: One keyword opens and connects
- **WHEN** a suite calls `Open BiDi Browser` with a target URL
- **THEN** a BiDi-enabled browser opens, SeleniumLibrary keywords (e.g. `Go To`, `Close Browser`) work on it, and BiDi keywords are usable immediately — with no separate helper file

#### Scenario: Attach to a separately opened browser
- **WHEN** a user opens the browser themselves with BiDi enabled and calls `Connect BiDi`
- **THEN** the adapter attaches to that browser via its `webSocketUrl` capability

### Requirement: Portable keyword naming across hosts
BiDi keyword names SHALL be kept recognizably parallel between the Browser adapter and the SeleniumLibrary adapter so suites can move between the two libraries with minimal changes.

#### Scenario: Familiar keyword between libraries
- **WHEN** a test author moves a BiDi-using scenario from a Browser suite to a SeleniumLibrary suite
- **THEN** the BiDi keyword names are the same or clearly analogous, minimizing rewrite
