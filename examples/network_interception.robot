*** Settings ***
Documentation     Network interception/mocking with WebDriver BiDi: stub responses,
...               inject faults and headers, answer auth, control caching, and read
...               per-request timing. Covers BiDi Mock Response, BiDi Fail Request,
...               BiDi Inject Headers, BiDi Provide Auth, BiDi Set Cache Behavior,
...               Clear BiDi Intercepts, Get BiDi Response Timing.
Resource          bidi_setup.resource
Suite Setup       Open BiDi Demo Suite
Suite Teardown    Close BiDi Demo Suite
Test Setup        Reset BiDi Buffers
Test Teardown     Clear BiDi Intercepts

*** Test Cases ***
Mock A Response
    [Documentation]    Serve a stub instead of hitting the server.
    BiDi Mock Response    *://*/api/*    body={"userId": 999}
    Visit                 index.html
    ${uid}=    BiDi Evaluate    fetch('/api/data.json').then(r => r.json()).then(d => d.userId)
    Should Be Equal As Integers    ${uid}    999

Inject A Fault
    [Documentation]    Force a request to fail to exercise error handling.
    BiDi Fail Request    *://*/api/*
    Visit                index.html
    ${err}=    BiDi Evaluate    fetch('/api/data.json').then(() => 'ok', e => 'FAILED:' + e.name)
    Should Start With    ${err}    FAILED

Inject Request Headers
    [Documentation]    Add a header to matching requests; the echo route returns it.
    BiDi Inject Headers    *://*/echo-headers    ${HDR}
    Visit                  index.html
    ${seen}=    BiDi Evaluate    fetch('/echo-headers').then(r => r.json()).then(d => d.headers['x-bidi-test'])
    Should Be Equal    ${seen}    injected

Answer An Auth Challenge
    [Documentation]    The /auth route returns 401 until Basic credentials are supplied.
    BiDi Provide Auth    *://*/auth    demo    secret
    Visit                auth
    ${body}=    Get BiDi DOM Snapshot
    Should Contain    ${body}    authed

Control Cache Behavior
    [Documentation]    Bypass the HTTP cache for caching-correctness tests.
    BiDi Set Cache Behavior    bypass
    Visit                      index.html
    Wait For BiDi Response     *index.html

Clearing Intercepts Restores Real Responses
    [Documentation]    After clearing, requests reach the real server again.
    BiDi Mock Response    *://*/api/*    body={"userId": 999}
    Visit                 index.html
    ${mocked}=    BiDi Evaluate    fetch('/api/data.json').then(r => r.json()).then(d => d.userId)
    Should Be Equal As Integers    ${mocked}    999
    Clear BiDi Intercepts
    ${real}=    BiDi Evaluate    fetch('/api/data.json').then(r => r.json()).then(d => d.userId)
    Should Be Equal As Integers    ${real}    42

Assert Per Request Timing
    [Documentation]    FetchTimingInfo-derived TTFB for a request, in milliseconds.
    Visit                       index.html
    Wait For BiDi Response      *index.html
    Get BiDi Response Timing    *index.html    ttfb    less than    ${5000}

*** Variables ***
&{HDR}    x-bidi-test=injected
