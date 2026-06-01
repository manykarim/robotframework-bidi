*** Settings ***
Documentation     Cookies, Core-Web-Vitals-style timing, and screenshots via BiDi.
Resource          bidi_setup.resource
Library           OperatingSystem
Suite Setup       Open BiDi Demo Suite
Suite Teardown    Close BiDi Demo Suite
Test Setup        Reset BiDi Buffers

*** Test Cases ***
Read Cookies Set By The Page
    [Documentation]    index.html sets demo_session=abc123 on load.
    Visit                  index.html
    Wait For BiDi Log Entry    text=home page loaded
    ${all}=    Get BiDi Cookies
    Should Not Be Empty    ${all}
    ${session}=    Get BiDi Cookies    name=demo_session
    Should Be Equal        ${session}[0][value]    abc123

Measure User Experience Timing
    [Documentation]    Web Vitals: TTFB / DOMContentLoaded / load / FCP (ms).
    Visit               app.html
    Wait For BiDi Response    *app.html
    ${vitals}=    Get BiDi Web Vitals
    Should Be True      $vitals['ttfb'] is not None
    Should Be True      $vitals['fcp'] is not None

Capture Screenshots
    [Documentation]    Returns base64 PNG, and can write a full-page file.
    Visit               app.html
    ${data}=    Take BiDi Screenshot
    Should Be True      len($data) > 100
    ${path}=    Take BiDi Screenshot    filename=${OUTPUT_DIR}/bidi_app.png    full_page=True
    File Should Exist   ${path}
