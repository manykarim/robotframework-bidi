# bidi-script-evaluation Specification

## Purpose
TBD: created by syncing change 'browser-bidi-extension'. Update Purpose to describe this capability.

## Requirements

### Requirement: Evaluate scripts in a realm
The extension SHALL provide a `BiDi Evaluate` keyword that evaluates an expression (or calls a function) in a specified BiDi realm or browsing context via the BiDi `script` module, returning the JSON-serialisable result. When no realm is specified, evaluation SHALL target the realm of the correlated current page.

#### Scenario: Evaluate in the default realm
- **WHEN** a user calls `BiDi Evaluate` with an expression and no explicit realm
- **THEN** the expression is evaluated in the realm of the correlated current page and its serialisable result is returned

#### Scenario: Evaluate in a specified realm
- **WHEN** a user calls `BiDi Evaluate` with an expression and an explicit realm or context (including an isolated sandbox realm)
- **THEN** the expression is evaluated in that realm and its result is returned

#### Scenario: Evaluation error is surfaced
- **WHEN** the evaluated script throws
- **THEN** the keyword fails with the script's error details rather than returning a misleading value

### Requirement: Register preload scripts
The extension SHALL provide a `BiDi Add Preload Script` keyword that registers a function body via BiDi `script.addPreloadScript` so it runs before page scripts, with optional realm targeting.

#### Scenario: Preload script runs before page scripts
- **WHEN** a user registers a preload script via `BiDi Add Preload Script` and then a page loads
- **THEN** the registered script executes before the page's own scripts run
