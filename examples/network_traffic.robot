*** Settings ***
Documentation     Realistic network observability with WebDriver BiDi:
...               inspect requests/responses, bodies, headers, counts, and timings.
Resource          bidi_setup.resource
Suite Setup       Open BiDi Demo Suite
Suite Teardown    Close BiDi Demo Suite
Test Setup        Reset BiDi Buffers

*** Test Cases ***
Inspect An API Response End To End
    [Documentation]    Wait for an XHR/fetch response, then assert status, headers and body.
    Visit                       index.html
    ${resp}=    Wait For BiDi Response    *api/data.json    timeout=20
    Get BiDi Response Status    *api/data.json    ==           ${200}
    Get BiDi Response Headers   *api/data.json    contains     content-type
    ${body}=    Get BiDi Response Body    ${resp}[request][request]
    Should Contain              ${body}    "userId": 42

List And Count Captured Requests
    [Documentation]    A page with html+css+js+img+json yields several network events.
    Visit                          index.html
    Wait For BiDi Response         *api/data.json    timeout=20
    Get BiDi Network Event Count   greater than    ${3}
    ${events}=    Get BiDi Network Events    url_glob=*.json
    Should Not Be Empty            ${events}

Measure Per Resource Timings
    [Documentation]    BiDi exposes DNS/connect/TLS/TTFB/download/total per resource.
    Visit                          index.html
    Wait For BiDi Response         *style.css    timeout=20
    ${timings}=    Get BiDi Resource Timings    url_glob=*style.css
    Should Not Be Empty            ${timings}
    Should Be True                 $timings[0]['total'] is not None

Find The Slowest And Largest Resources
    [Documentation]    Top-N performance analysis: slowest-loading and biggest resources.
    ...                Flexible via top/phase/url_glob, but readable and simple.
    Visit    index.html
    Wait For BiDi Response    *style.css    timeout=20
    ${slowest}=    Get BiDi Slowest Resources    top=5    url_glob=*127.0.0.1*
    Should Not Be Empty    ${slowest}
    Should Be True    $slowest[0]['total'] is not None
    # Slowest first (descending by total load time).
    Should Be True    ($slowest[0]['total'] or 0) >= ($slowest[-1]['total'] or 0)
    # Top 3 slowest specifically by time-to-first-byte:
    Get BiDi Slowest Resources    top=3    phase=ttfb    url_glob=*127.0.0.1*
    # Biggest transfers (bytes), largest first:
    ${largest}=    Get BiDi Largest Resources    top=5    url_glob=*127.0.0.1*
    Should Not Be Empty    ${largest}
    Should Be True    $largest[0]['size'] >= $largest[-1]['size']

Subscribe And Unsubscribe Control Capture
    [Documentation]    Unsubscribing stops new network events from being buffered.
    BiDi Unsubscribe               network.beforeRequestSent, network.responseCompleted
    Visit                          index.html
    Sleep                          1s
    Get BiDi Network Event Count   ==    ${0}
    [Teardown]    BiDi Subscribe   network.beforeRequestSent, network.responseCompleted
