*** Settings ***
Documentation     Environment emulation with WebDriver BiDi: geolocation, locale,
...               timezone, user-agent, viewport, plus gating for commands an engine
...               does not implement. Covers BiDi Set Geolocation/Locale/Timezone/
...               User Agent/Viewport/Forced Colors/Scripting Enabled and Get BiDi
...               Support Matrix.
Resource          bidi_setup.resource
Suite Setup       Open BiDi Demo Suite
Suite Teardown    Close BiDi Demo Suite
Test Setup        Reset BiDi Buffers

*** Test Cases ***
Override Locale And Timezone
    [Documentation]    i18n date/number formatting without a VPN or OS change.
    BiDi Set Locale       fr-FR
    BiDi Set Timezone     Asia/Tokyo
    Visit                 index.html
    BiDi Evaluate    Intl.DateTimeFormat().resolvedOptions().timeZone    ==    Asia/Tokyo
    BiDi Evaluate    Intl.NumberFormat().resolvedOptions().locale        ==    fr-FR

Override The User Agent
    [Documentation]    Device/browser spoofing.
    BiDi Set User Agent    BiDiBot/1.0 (Example)
    Visit                  index.html
    BiDi Evaluate    navigator.userAgent    contains    BiDiBot/1.0

Override Geolocation
    [Documentation]    Geo-gated UX testing (override is applied to the context).
    BiDi Set Geolocation    48.2082    16.3738
    Visit                   index.html
    # The override is now active; pages that read navigator.geolocation see Vienna.

Set An Exact Viewport
    [Documentation]    Deterministic viewport for reproducible visual baselines.
    Visit               index.html
    BiDi Set Viewport    800    600
    BiDi Evaluate        window.innerWidth    ==    ${800}

Unsupported Overrides Fail Fast With A Clear Message
    [Documentation]    Capability gating: forced-colors and scripting-enabled are
    ...                not implemented on this Chromium and fail fast (not hang).
    Visit    index.html
    Run Keyword And Expect Error    *not supported*    BiDi Set Forced Colors      dark
    Run Keyword And Expect Error    *not supported*    BiDi Set Scripting Enabled    ${False}

Read The Capability Support Matrix
    [Documentation]    Per-engine support + the versions it was validated against.
    ${matrix}=    Get BiDi Support Matrix
    Should Contain    ${matrix}    support
    Should Contain    ${matrix}    tested_against
