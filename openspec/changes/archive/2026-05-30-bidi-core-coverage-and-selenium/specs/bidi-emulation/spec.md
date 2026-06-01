## ADDED Requirements

### Requirement: Environment overrides
The extension SHALL provide keywords to apply BiDi `emulation` overrides for the current (or a specified) context: geolocation, locale, timezone, user-agent, and forced-colors mode. Each override SHALL be scoped and reversible within the run.

#### Scenario: Override geolocation
- **WHEN** a user sets a geolocation override and the page reads `navigator.geolocation`
- **THEN** the page observes the overridden coordinates

#### Scenario: Override locale and timezone for i18n
- **WHEN** a user sets locale and timezone overrides
- **THEN** locale-sensitive date/number formatting on the page reflects the overrides without a VPN or OS change

### Requirement: Network conditions and responsive overrides
The extension SHALL support `setNetworkConditions` (throttle/offline), viewport sizing (`browsingContext.setViewport`), and screen/orientation/scrollbar/touch overrides for performance, offline-UX, and responsive-design testing.

#### Scenario: Simulate offline
- **WHEN** a user enables offline emulation and the page performs a fetch
- **THEN** the fetch fails as offline, exercising the page's offline handling

#### Scenario: Exact viewport for visual baselines
- **WHEN** a user sets a viewport size
- **THEN** the page renders at exactly that viewport (chrome excluded), improving visual-test reproducibility

### Requirement: Accessibility and degradation overrides
The extension SHALL support forced-colors (High Contrast) emulation and `setScriptingEnabled` to validate accessibility rendering and no-JavaScript graceful degradation.

#### Scenario: Forced-colors rendering
- **WHEN** a user enables forced-colors emulation
- **THEN** the page renders in forced-colors mode for accessibility assertions
