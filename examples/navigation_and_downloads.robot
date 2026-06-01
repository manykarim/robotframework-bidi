*** Settings ***
Documentation     Navigation-lifecycle events (incl. SPA route changes) and managed
...               downloads with WebDriver BiDi. Covers Wait For BiDi Navigation,
...               Get BiDi Navigation Events, BiDi Set Download Behavior,
...               Wait For BiDi Download.
Resource          bidi_setup.resource
Suite Setup       Open BiDi Demo Suite
Suite Teardown    Close BiDi Demo Suite
Test Setup        Reset BiDi Buffers

*** Test Cases ***
Capture Navigation Lifecycle Events
    [Documentation]    Read 'load' events and detect an SPA history change.
    BiDi Subscribe    browsingContext.load, browsingContext.historyUpdated
    Visit             app.html
    ${loads}=    Get BiDi Navigation Events    load
    Should Not Be Empty    ${loads}
    # Trigger a client-side route change (history.pushState) and wait for it.
    BiDi Evaluate     document.getElementById('spa').click()
    ${hist}=    Wait For BiDi Navigation    historyUpdated    timeout=10
    Should Contain    ${hist}[url]    route2

Wait For A Managed Download
    [Documentation]    Configure downloads and wait for completion.
    BiDi Set Download Behavior    ${OUTPUT_DIR}
    Visit                         index.html
    # Trigger a download of the /download attachment route.
    BiDi Evaluate    (() => { const a = document.createElement('a'); a.href = '/download/report.txt'; a.download = 'report.txt'; document.body.appendChild(a); a.click(); return 1; })()
    ${done}=    Wait For BiDi Download    timeout=20
    Should Not Be Empty    ${done}
