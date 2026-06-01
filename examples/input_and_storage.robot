*** Settings ***
Documentation     Input gestures, file uploads, and cookie writes with WebDriver BiDi.
...               Covers BiDi Set Files, BiDi Perform Actions, BiDi Wheel Scroll,
...               BiDi Set Cookie, BiDi Delete Cookies.
Resource          bidi_setup.resource
Library           OperatingSystem
Suite Setup       Open BiDi Demo Suite
Suite Teardown    Close BiDi Demo Suite
Test Setup        Reset BiDi Buffers

*** Test Cases ***
Upload A File To A Hidden Input
    [Documentation]    input.setFiles works on hidden file inputs.
    Create File          ${OUTPUT_DIR}/upload.txt    hello bidi upload
    Visit                app.html
    BiDi Set Files       css    \#upload    ${OUTPUT_DIR}/upload.txt
    BiDi Evaluate        document.querySelector('#upload').files.length    ==    ${1}

Scroll With The Wheel
    [Documentation]    A convenience wheel gesture (input.performActions under the hood).
    Visit              tall.html
    BiDi Wheel Scroll    0    800
    Sleep              0.3s
    BiDi Evaluate        window.scrollY > 0    ==    ${True}

Perform A Raw Actions Sequence
    [Documentation]    Full Actions API: a wheel source list via BiDi Perform Actions.
    Visit              tall.html
    ${actions}=    Evaluate
    ...    [{"type":"wheel","id":"w","actions":[{"type":"scroll","x":0,"y":0,"deltaX":0,"deltaY":600}]}]
    BiDi Perform Actions    ${actions}
    Sleep              0.3s
    BiDi Evaluate        window.scrollY > 0    ==    ${True}

Seed And Delete Cookies
    [Documentation]    Seed an auth cookie to skip login, then delete it.
    BiDi Set Cookie     auth    tok-123    127.0.0.1
    Visit               index.html
    ${seeded}=    Get BiDi Cookies    name=auth
    Should Be Equal     ${seeded}[0][value]    tok-123
    BiDi Delete Cookies    name=auth
    ${gone}=    Get BiDi Cookies    name=auth
    Should Be Empty     ${gone}
