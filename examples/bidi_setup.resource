*** Settings ***
Documentation     Shared setup for the Browser-BiDi example suites.
...
...               Launches a driverless Chrome + a local HTTP server for the
...               `pages/` fixtures, connects Playwright (CDP) and BiDi (mapper)
...               once per suite, and gives each test a clean buffer + a tracked
...               page so navigations are captured reliably.
Library           BiDiBrowserLauncher.py
Library           Browser    plugins=${EXECDIR}/Browser_BiDi/BrowserBiDi.py

*** Keywords ***
Open BiDi Demo Suite
    [Documentation]    Suite Setup: launch, connect, subscribe, warm up a tracked page.
    Start BiDi Browser
    Connect To Browser    ${CDP_URL}    use_cdp=True
    # Generous navigation timeout so transient slowness (many suites under one
    # `robot examples` run, driverless mapper warmup) doesn't fail page.goto.
    Set Browser Timeout    30 seconds
    Connect BiDi          ${BIDI_URL}    browser=chromium    transport=${BIDI_TRANSPORT}
    BiDi Subscribe        network.beforeRequestSent, network.responseCompleted, log.entryAdded
    New Page              about:blank

Close BiDi Demo Suite
    [Documentation]    Suite Teardown.
    Run Keyword And Ignore Error    Disconnect BiDi
    Run Keyword And Ignore Error    Close Browser
    Stop BiDi Browser

Reset BiDi Buffers
    [Documentation]    Test Setup: clean counts/events between scenarios.
    Clear BiDi Buffers

Visit
    [Documentation]    Navigate the tracked page to a fixture and return its URL.
    [Arguments]    ${path}
    ${url}=    Set Variable    ${BASE_URL}${path}
    Go To      ${url}
    RETURN     ${url}
