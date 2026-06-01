*** Settings ***
Documentation     SeleniumLibrary + WebDriver BiDi over the shared bidi_core engine,
...               exercising every Selenium-BiDi keyword. The adapter opens and connects
...               the BiDi-enabled browser itself via `Open BiDi Browser` — no helper
...               library needed. Keyword names match the Browser-BiDi adapter so suites
...               are portable between the two libraries.
...
...               ``${CHROMEDRIVER}`` is optional: empty uses Selenium Manager to fetch a
...               matching driver; set it to a chromedriver path to use a local one.
Library           SeleniumLibrary    plugins=${EXECDIR}/Selenium_BiDi/SeleniumBiDi.py
Suite Setup       Open Selenium BiDi Session
Suite Teardown    Run Keywords    Disconnect BiDi    AND    Close All Browsers
Test Setup        Reset Selenium BiDi

*** Variables ***
${CHROMEDRIVER}      ${EMPTY}
${SITE}              https://example.com/

*** Test Cases ***
Page Identity And Evaluation
    [Documentation]    Read the page over BiDi, correlated to the Selenium window.
    Get BiDi Title                       ==    Example Domain
    Get BiDi Url                         contains    example.com
    Get BiDi Element Count    css    h1    ==    ${1}
    BiDi Evaluate    document.querySelector('h1').textContent    ==    Example Domain
    ${ctx}=    Get BiDi Context For Current Page
    Should Not Be Empty    ${ctx}
    # ARIA snapshot (role + accessible name) — cross-engine via BiDi, no Playwright.
    Get BiDi Aria Snapshot    contains    - heading "Example Domain"

Real Time Console And Error Capture
    [Documentation]    Cross-browser console/error capture — SeleniumLibrary has none natively.
    BiDi Evaluate    console.log('selenium-bidi-marker'); 1
    Wait For BiDi Log Entry    text=selenium-bidi-marker
    ${logs}=    Get BiDi Console Log
    Should Not Be Empty    ${logs}
    # Search/filter console output by substring or regex.
    ${hits}=    Get BiDi Console Log    pattern=selenium-\\w+-marker
    Should Not Be Empty    ${hits}
    Get BiDi JS Error Count    ==    ${0}
    ${errors}=    Get BiDi JS Errors
    Should Be Empty    ${errors}
    BiDi Unsubscribe    log.entryAdded
    Clear BiDi Buffers
    BiDi Subscribe      log.entryAdded

Network Observe Mock And Fault
    [Documentation]    Inspect responses and stub/fault requests (no proxy needed).
    ${resp}=    Wait For BiDi Response    *example.com*
    Get BiDi Response Status    *example.com*    ==    ${200}
    ${body}=    Get BiDi Response Body    ${resp}[request][request]
    Should Contain    ${body}    Example Domain
    ${events}=    Get BiDi Network Events
    Should Not Be Empty    ${events}
    # Top-N performance analysis (slowest/largest), readable and flexible.
    ${slow}=    Get BiDi Slowest Resources    top=5
    Should Not Be Empty    ${slow}
    ${big}=     Get BiDi Largest Resources     top=5
    Should Not Be Empty    ${big}
    # Same-origin mock + fault.
    BiDi Mock Response    *://example.com/api/*    body={"ok": true}
    ${ok}=    BiDi Evaluate    fetch('/api/x').then(r => r.json()).then(d => d.ok)
    Should Be Equal    ${ok}    ${True}
    BiDi Fail Request     *://example.com/down*
    ${err}=    BiDi Evaluate    fetch('/down').then(() => 'ok', () => 'FAILED')
    Should Be Equal    ${err}    FAILED
    Clear BiDi Intercepts

Emulation And Isolated Contexts
    [Documentation]    i18n overrides and hermetic user-context isolation.
    BiDi Set Locale       fr-FR
    BiDi Set Timezone     Asia/Tokyo
    BiDi Evaluate    Intl.DateTimeFormat().resolvedOptions().timeZone    ==    Asia/Tokyo
    ${uc}=    New BiDi User Context
    Should Not Be Empty    ${uc}
    Remove BiDi User Context    ${uc}

*** Keywords ***
Open Selenium BiDi Session
    Open BiDi Browser    ${SITE}    browser=chrome    executable_path=${CHROMEDRIVER}
    BiDi Subscribe       log.entryAdded, network.responseCompleted

Reset Selenium BiDi
    Clear BiDi Buffers
    Run Keyword And Ignore Error    Clear BiDi Intercepts
    Go To    ${SITE}
