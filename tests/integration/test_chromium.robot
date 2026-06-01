*** Settings ***
Documentation    Chromium integration: BiDi session, correlation, network, log (task 6.6).
...              Requires a Chromium launched with CDP + BiDi reachable.
Library          Browser    plugins=${EXECDIR}/Browser_BiDi/BrowserBiDi.py
Suite Teardown   Run Keyword And Ignore Error    Close Browser

*** Variables ***
${CDP_URL}       http://localhost:9222
${BIDI_URL}      ws://localhost:9222/session
${PAGE_URL}      https://example.com/

*** Test Cases ***
Connect And Resolve Context For Current Page
    Connect To Browser    ${CDP_URL}    use_cdp=True
    Connect BiDi          ${BIDI_URL}    browser=chromium
    New Page              ${PAGE_URL}
    ${ctx}=    Get BiDi Context For Current Page
    Should Not Be Empty    ${ctx}
    [Teardown]    Disconnect BiDi

Capture Network Events And Body
    Connect To Browser    ${CDP_URL}    use_cdp=True
    Connect BiDi          ${BIDI_URL}    browser=chromium
    BiDi Subscribe        network.responseCompleted
    New Page              ${PAGE_URL}
    ${events}=    Get BiDi Network Events
    Should Not Be Empty    ${events}
    ${body}=    Get BiDi Response Body    ${events}[0][request][request]
    Should Not Be Empty    ${body}
    [Teardown]    Disconnect BiDi

Capture Console Log
    Connect To Browser    ${CDP_URL}    use_cdp=True
    Connect BiDi          ${BIDI_URL}    browser=chromium
    BiDi Subscribe        log.entryAdded
    New Page              ${PAGE_URL}
    Evaluate JavaScript    ${None}    () => console.log('bidi-integration-marker')
    ${entry}=    Wait For BiDi Log Entry    text=bidi-integration-marker    timeout=10
    Should Be Equal    ${entry}[text]    bidi-integration-marker
    [Teardown]    Disconnect BiDi
