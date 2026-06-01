*** Settings ***
Documentation     Read page identity and DOM via BiDi, including open shadow DOM
...               and iframe (separate browsing context) content.
Resource          bidi_setup.resource
Suite Setup       Open BiDi Demo Suite
Suite Teardown    Close BiDi Demo Suite
Test Setup        Reset BiDi Buffers

*** Test Cases ***
Read Page Identity
    Visit               app.html
    Get BiDi Url        contains    app.html
    Get BiDi Title      ==          BiDi Demo App

Locate Elements And Read Text
    Visit                    app.html
    Get BiDi Element Count   css    .todo    ==    ${3}
    Get BiDi Element Text    css    h1       ==    BiDi Demo App
    ${items}=    Get BiDi Elements    css    .todo
    Length Should Be         ${items}    ${3}
    Should Be Equal          ${items}[0][localName]    li

Locate By Accessibility Role
    [Documentation]    BiDi supports an accessibility locator (role/name).
    Visit                    app.html
    Get BiDi Element Count   accessibility    role=heading    greater than    ${0}

Read Open Shadow DOM
    [Documentation]    Plain CSS does not cross shadow roots; pierce_shadow does.
    Visit                    app.html
    Get BiDi Element Count   css    .shadow-action    ==    ${0}
    Get BiDi Element Count   css    .shadow-action    ==    ${1}    pierce_shadow=True
    Get BiDi Element Text    css    .shadow-label     ==    In Shadow    pierce_shadow=True

Inspect Iframe Content Via Its Context
    [Documentation]    Iframes are separate contexts; find the frame by URL and target it.
    Visit                    app.html
    Get BiDi Context For Current Page    # resolves the top page's context
    ${contexts}=    Get BiDi Contexts
    ${frame_ctx}=    Set Variable    ${EMPTY}
    FOR    ${c}    IN    @{contexts}
        IF    'frame.html' in $c['url']
            ${frame_ctx}=    Set Variable    ${c}[context]
        END
    END
    Should Not Be Empty      ${frame_ctx}
    Get BiDi Element Count   css    .frame-content    ==    ${1}    context=${frame_ctx}

Capture A DOM Snapshot
    Visit                    app.html
    ${html}=    Get BiDi DOM Snapshot
    Should Contain           ${html}    <demo-card
    Should Contain           ${html}    id="todos"

Read The Accessibility Tree
    [Documentation]    A Playwright-style ARIA snapshot (role + accessible name),
    ...                computed cross-engine via BiDi. Assert with `contains`.
    Visit                    app.html
    Get BiDi Aria Snapshot    contains    - heading "BiDi Demo App"
    Get BiDi Aria Snapshot    contains    - list
    # Snapshot just a subtree:
    Get BiDi Aria Snapshot    contains    - button "Sign in"    selector=#login
