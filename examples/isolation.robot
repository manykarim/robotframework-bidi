*** Settings ***
Documentation     Hermetic test isolation with BiDi user contexts (separate
...               cookies/storage/cache) without a fresh browser process. Covers
...               New BiDi User Context, New BiDi Context In User Context,
...               Remove BiDi User Context.
Resource          bidi_setup.resource
Suite Setup       Open BiDi Demo Suite
Suite Teardown    Close BiDi Demo Suite
Test Setup        Reset BiDi Buffers

*** Test Cases ***
Create Isolated User Contexts
    [Documentation]    Each user context has separate cookies/storage/cache.
    ${uc1}=    New BiDi User Context
    ${uc2}=    New BiDi User Context
    Should Not Be Empty    ${uc1}
    Should Not Be Equal    ${uc1}    ${uc2}

Open A Tab Inside A User Context
    [Documentation]    A browsing context created in a user context is a fresh,
    ...                isolated tab; it appears in the context tree.
    ${uc}=     New BiDi User Context
    ${ctx}=    New BiDi Context In User Context    ${uc}
    Should Not Be Empty    ${ctx}
    ${all}=    Get BiDi Contexts
    ${ids}=    Evaluate    [c['context'] for c in $all]
    Should Contain    ${ids}    ${ctx}
    [Teardown]    Remove BiDi User Context    ${uc}

Remove A User Context
    [Documentation]    Created contexts are auto-removed on Disconnect BiDi; you can
    ...                also remove one explicitly.
    ${uc}=    New BiDi User Context
    Remove BiDi User Context    ${uc}
