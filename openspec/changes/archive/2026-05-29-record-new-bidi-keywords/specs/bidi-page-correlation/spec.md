## ADDED Requirements

### Requirement: Enumerate browsing contexts
The extension SHALL provide a `Get BiDi Contexts` keyword that returns the flattened browsing-context tree — top-level pages and nested iframes — each entry exposing at least its context id and URL, so users can target a specific iframe's context for the element getters.

#### Scenario: List page and iframe contexts
- **WHEN** the current page contains an iframe and the user calls `Get BiDi Contexts`
- **THEN** the returned list includes both the top-level page context and the iframe's context, each with its context id and URL

#### Scenario: Target an iframe by its context
- **WHEN** a user selects the iframe's context id from `Get BiDi Contexts` and passes it to an element getter
- **THEN** the getter resolves nodes within that iframe
