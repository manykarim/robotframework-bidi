## 1. Verify implementation matches the recorded specs

- [x] 1.1 Confirm `Launch BiDi Browser` returns `{bidi_url, cdp_url, transport, browser}` and is driverless by default (chromium→`cdp-mapper`, firefox→`websocket`)
- [x] 1.2 Confirm `Close BiDi Browser` and the tracked teardown on `Disconnect BiDi` / atexit leave no orphaned browser, and never close an externally launched browser
- [x] 1.3 Confirm `Connect BiDi` accepts `transport=websocket|cdp-mapper` and the mapper path works without chromedriver
- [x] 1.4 Confirm `Clear BiDi Buffers` resets network/log counts
- [x] 1.5 Confirm `Get BiDi Contexts` returns the flattened page+iframe context tree with id and URL

## 2. Spec & docs alignment

- [x] 2.1 Ensure the delta specs (`bidi-session-management`, `bidi-page-correlation`) match the shipped keyword behaviour
- [x] 2.2 Ensure README keyword list and `examples/self_launching.robot` reference the keywords
- [x] 2.3 Regenerate libdoc so `Launch BiDi Browser` / `Close BiDi Browser` / `Clear BiDi Buffers` / `Get BiDi Contexts` appear

## 3. Tests

- [x] 3.1 Confirm unit tests cover `Clear BiDi Buffers` and `Get BiDi Contexts` (manager) and the mapper client
- [x] 3.2 Confirm `examples/self_launching.robot` validates launch + teardown live (Chromium + Firefox)

## 4. Archive

- [x] 4.1 On archive, sync the delta specs into `openspec/specs/` (MODIFIED requirements replace their originals; ADDED requirements appended)
