## ADDED Requirements

### Requirement: Realistic input gestures
The extension SHALL expose `input.performActions` for pointer, key, and wheel action sequences (hover, drag-and-drop, multi-touch, scroll-wheel) against the current context.

#### Scenario: Drag and drop
- **WHEN** a user issues a pointer action sequence that presses on a source, moves to a target, and releases
- **THEN** the page performs the drag-and-drop interaction

#### Scenario: Scroll-wheel
- **WHEN** a user issues a wheel action over an element
- **THEN** the element (or page) scrolls accordingly

### Requirement: File uploads and dialog detection
The extension SHALL set file inputs via `input.setFiles` (including hidden inputs) and SHALL allow detecting native file dialogs via the `input.fileDialogOpened` event.

#### Scenario: Upload to a hidden input
- **WHEN** a user sets files on a file input via `setFiles`
- **THEN** the input reflects the selected files without interacting with the OS dialog

#### Scenario: Detect a native file dialog
- **WHEN** an action opens a native file chooser and the user waits for the dialog event
- **THEN** the extension reports that a file dialog opened
