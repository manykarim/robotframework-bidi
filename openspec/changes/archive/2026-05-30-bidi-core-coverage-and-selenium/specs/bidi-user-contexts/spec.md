## ADDED Requirements

### Requirement: Create and remove isolated user contexts
The extension SHALL provide keywords to create and remove BiDi user contexts (`browser.createUserContext`/`removeUserContext`), each with separated cookies, storage, and cache, for fast hermetic test isolation. Created user contexts SHALL be tracked and removed on teardown so none leak between runs.

#### Scenario: Create an isolated context
- **WHEN** a user creates a new user context
- **THEN** a context id is returned whose cookies and storage are isolated from other user contexts

#### Scenario: Isolation between two contexts
- **WHEN** a cookie is set in one user context and read from another
- **THEN** the second context does not see the first context's cookie

#### Scenario: Teardown removes created contexts
- **WHEN** the session ends with user contexts still open
- **THEN** the extension removes the contexts it created, leaving no orphaned isolation state
