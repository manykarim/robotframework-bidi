*** Settings ***
Documentation     The extension launches its own BiDi-reachable browser — no
...               chromedriver/geckodriver, no external launcher script. Uses only
...               Browser-BiDi keywords (`Launch BiDi Browser` / `Close BiDi Browser`).
Library           Browser    plugins=${EXECDIR}/Browser_BiDi/BrowserBiDi.py

*** Test Cases ***
Driverless Chromium: Launch, Connect, Observe
    [Documentation]    Full Strategy-1 from one keyword: Playwright over CDP +
    ...                BiDi via the bundled mapper on the same launched browser.
    ${b}=    Launch BiDi Browser    chromium    no_sandbox=True
    Should Be Equal       ${b}[transport]    cdp-mapper
    Connect To Browser    ${b}[cdp_url]      use_cdp=True
    Connect BiDi          ${b}[bidi_url]     transport=${b}[transport]
    BiDi Subscribe        network.responseCompleted
    New Page              about:blank        # warm up the tracked page
    Go To                 https://example.com/
    Wait For BiDi Response      *example.com*
    Get BiDi Response Status    *example.com*    ==    ${200}
    Get BiDi Title              ==    Example Domain
    # Disconnect BiDi also tears down the browser we launched.
    [Teardown]    Run Keywords    Close Browser    AND    Disconnect BiDi

Driverless Firefox: Launch And Connect
    [Documentation]    Firefox native driverless BiDi (no geckodriver). Read-only
    ...                BiDi works without Playwright; here we list the context tree.
    ${b}=    Launch BiDi Browser    firefox
    Should Be Equal    ${b}[transport]    websocket
    Connect BiDi       ${b}[bidi_url]    browser=firefox    transport=${b}[transport]
    ${contexts}=    Get BiDi Contexts
    Should Not Be Empty    ${contexts}
    # Close BiDi Browser explicitly tears down the launched Firefox.
    [Teardown]    Run Keywords    Disconnect BiDi    AND    Close BiDi Browser
