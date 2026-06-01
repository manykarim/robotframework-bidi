## ADDED Requirements

### Requirement: SeleniumLibrary BiDi keyword adapter
The extension SHALL provide a SeleniumLibrary-compatible keyword layer over `bidi_core` that connects a BiDi session to the browser SeleniumLibrary is driving, exposing the high-value BiDi capabilities (network observe/mock, log, user contexts, emulation, preload) to SeleniumLibrary suites. It SHALL NOT require the Browser library.

#### Scenario: Use BiDi from a SeleniumLibrary suite
- **WHEN** a SeleniumLibrary suite imports the BiDi layer and connects after opening a browser
- **THEN** BiDi keywords (e.g. subscribe to logs, mock a response) work against the Selenium-driven browser without the Browser library installed

#### Scenario: No native equivalent regression
- **WHEN** a SeleniumLibrary suite asserts no console errors during a journey via the BiDi log keyword
- **THEN** it captures errors cross-browser in real time, which SeleniumLibrary cannot do natively

### Requirement: Portable keyword naming across hosts
BiDi keyword names SHALL be kept recognizably parallel between the Browser adapter and the SeleniumLibrary adapter so suites can move between the two libraries with minimal changes.

#### Scenario: Familiar keyword between libraries
- **WHEN** a test author moves a BiDi-using scenario from a Browser suite to a SeleniumLibrary suite
- **THEN** the BiDi keyword names are the same or clearly analogous, minimizing rewrite
