# bidi-storage-management Specification

## Purpose
TBD: created by syncing change 'bidi-core-coverage-and-selenium'. Update Purpose to describe this capability.

## Requirements

### Requirement: Write and delete cookies
The extension SHALL provide keywords to set and delete cookies via BiDi `storage.setCookie`/`deleteCookies`, with `PartitionKey` awareness, complementing the existing read-only cookie getter. Seeding an authentication cookie SHALL be possible so tests can skip login flows.

#### Scenario: Seed an auth cookie
- **WHEN** a user sets an authentication cookie before navigating
- **THEN** the page loads in an authenticated state without performing the login flow

#### Scenario: Delete cookies by filter
- **WHEN** a user deletes cookies matching a name/domain filter
- **THEN** those cookies are removed and a subsequent read does not return them

#### Scenario: Partition-aware operations
- **WHEN** a user sets or reads a cookie with a partition key
- **THEN** the operation targets the specified partition rather than the default
