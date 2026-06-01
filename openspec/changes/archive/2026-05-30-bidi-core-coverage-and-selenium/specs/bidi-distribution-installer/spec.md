## ADDED Requirements

### Requirement: Pip-installable distribution with optional adapters
The project SHALL be installable from a pip distribution, with the framework-neutral `bidi_core` always present and the host adapters available as optional extras (e.g. `[browser]`, `[selenium]`) so users install only what they need. The vendored chromium-bidi mapper SHALL ship as package data so driverless Chrome works offline.

#### Scenario: Install the Selenium adapter only
- **WHEN** a user installs the package with the `selenium` extra and not the `browser` extra
- **THEN** the SeleniumLibrary BiDi layer is available and the Browser library is not required

### Requirement: Custom init installer
The package SHALL expose a console-script `init` command that provisions the runtime: refresh/align the vendored mapper to the local Chrome, and optionally fetch matching drivers and/or browsers. `init` SHALL be explicit (never run automatically on import), opt-in per artifact, and verify integrity of anything it downloads.

#### Scenario: Initialize the mapper
- **WHEN** a user runs the `init` command
- **THEN** the chromium-bidi mapper aligned to the local Chrome is made available without manual file handling

#### Scenario: Optional driver fetch is opt-in
- **WHEN** a user runs `init` without requesting drivers
- **THEN** no driver or browser is downloaded, and the mapper-only setup still enables driverless Chrome and native Firefox

### Requirement: Capability gating and support matrix
Each control-side keyword SHALL check support for the active browser/engine before issuing its BiDi command and fail fast with an actionable message when unsupported. The package SHALL ship a documented support matrix that gating reads from, reflecting the Editor's-Draft maturity and engine divergence.

#### Scenario: Unsupported command fails clearly
- **WHEN** a user calls a keyword whose BiDi command is unsupported on the active engine/version
- **THEN** the keyword fails fast with a clear message naming the command, the engine, and a suggested alternative, rather than hanging or erroring obscurely
