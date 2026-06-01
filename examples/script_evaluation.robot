*** Settings ***
Documentation     Evaluate JavaScript in the page realm and inject preload scripts via BiDi.
Resource          bidi_setup.resource
Suite Setup       Open BiDi Demo Suite
Suite Teardown    Close BiDi Demo Suite
Test Setup        Reset BiDi Buffers

*** Test Cases ***
Evaluate Expression In The Page
    [Documentation]    app.js sets window.__appLoaded; read it back over BiDi.
    Visit            index.html
    BiDi Evaluate    window.__appLoaded                       ==    ${True}
    BiDi Evaluate    document.querySelector('h1').textContent    ==    BiDi Demo Home

Evaluate Returns Structured Data
    [Documentation]    Return values serialise to native Robot types.
    Visit            app.html
    BiDi Evaluate    document.querySelectorAll('.todo').length    ==    ${3}
    ${title}=    BiDi Evaluate    document.title
    Should Be Equal    ${title}    BiDi Demo App

Inject A Preload Script Before Page Scripts
    [Documentation]    addPreloadScript runs before the page's own scripts on next load.
    BiDi Add Preload Script    () => { window.__bidiPreload = 'injected-by-bidi'; }
    Visit            app.html
    BiDi Evaluate    window.__bidiPreload    ==    injected-by-bidi
