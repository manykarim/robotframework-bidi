*** Settings ***
Documentation    Self-contained example for the Browser-BiDi plugin.
...
...              Suite Setup launches a headless Chromium exposing BOTH a CDP endpoint
...              and a BiDi WebSocket (via the bundled launcher) and publishes ${CDP_URL}
...              / ${BIDI_URL}. Requires `chromedriver` on PATH (matching your Chrome);
...              the suite skips gracefully if it is missing.
...
...              Run from the repo root so the plugin/package import resolves:
...                PYTHONPATH=. uv run robot -d results examples/bidi_example.robot
Library          BiDiBrowserLauncher.py
Library          Browser    plugins=${EXECDIR}/Browser_BiDi/BrowserBiDi.py
Suite Setup      Start BiDi Browser
Suite Teardown   Run Keywords    Close Browser    AND    Stop BiDi Browser

*** Variables ***
${APP_URL}       https://example.com/

*** Test Cases ***
Capture Real Network Bodies
    [Documentation]    Headline capability: retrieve a response body via BiDi.
    Connect To Browser    ${CDP_URL}    use_cdp=True
    Connect BiDi          ${BIDI_URL}    browser=chromium    transport=${BIDI_TRANSPORT}
    BiDi Subscribe        network.responseCompleted, log.entryAdded
    New Page              ${APP_URL}
    ${resp}=    Wait For BiDi Response    *example.com*
    ${body}=    Get BiDi Response Body    ${resp}[request][request]
    Should Contain        ${body}    Example Domain
    [Teardown]    Disconnect BiDi

Assert No Uncaught JS Errors
    Connect To Browser    ${CDP_URL}    use_cdp=True
    Connect BiDi          ${BIDI_URL}    browser=chromium    transport=${BIDI_TRANSPORT}
    BiDi Subscribe        log.entryAdded
    New Page              ${APP_URL}
    Get BiDi JS Error Count    ==    ${0}
    [Teardown]    Disconnect BiDi

Getter And Assertion In One Call
    [Documentation]    AssertionEngine-style getter+assert (Browser library pattern).
    Connect To Browser    ${CDP_URL}    use_cdp=True
    Connect BiDi          ${BIDI_URL}    browser=chromium    transport=${BIDI_TRANSPORT}
    BiDi Subscribe        network.responseCompleted
    New Page              ${APP_URL}
    Wait For BiDi Response      *example.com*
    Get BiDi Response Status    *example.com*    ==    ${200}
    Get BiDi Title              ==    Example Domain
    Get BiDi Element Count      css    h1    ==    ${1}
    [Teardown]    Disconnect BiDi
