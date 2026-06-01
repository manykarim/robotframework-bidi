*** Settings ***
Documentation     Console log and uncaught-exception observability with WebDriver BiDi.
Resource          bidi_setup.resource
Suite Setup       Open BiDi Demo Suite
Suite Teardown    Close BiDi Demo Suite
Test Setup        Reset BiDi Buffers

*** Test Cases ***
Capture Console Messages
    [Documentation]    Wait for a specific console line, then read the full log.
    Visit                       index.html
    ${entry}=    Wait For BiDi Log Entry    text=home page loaded    timeout=20
    Should Be Equal             ${entry}[text]    home page loaded
    Get BiDi Console Log Count    greater than    ${0}

Filter Console By Level
    [Documentation]    The app page emits a console.warn; filter for it.
    Visit                       app.html
    Wait For BiDi Log Entry     text=app page loaded    timeout=20
    ${warnings}=    Get BiDi Console Log    level=warn
    Should Not Be Empty         ${warnings}
    Should Contain              ${warnings}[0][text]    demo warning

Detect Uncaught JavaScript Errors
    [Documentation]    The errors page throws a ReferenceError and a timed Error.
    Visit                       errors.html
    Wait For BiDi Log Entry     text=Intentional demo error    timeout=15
    Get BiDi JS Error Count     greater than    ${0}
    ${errors}=    Get BiDi JS Errors
    Should Contain              ${errors}[0][text]    Error

A Clean Page Has No JS Errors
    [Documentation]    Assert the happy path is error-free. (Go To already waits
    ...                for load, so no console-event wait is needed here.)
    Visit                       index.html
    Get BiDi JS Error Count     ==    ${0}

Search Console Messages By Text And Pattern
    [Documentation]    Filter/search console output by substring or regex.
    Visit             app.html
    Wait For BiDi Log Entry    text=app page loaded    timeout=20
    BiDi Evaluate     console.log('order-987 created'); console.error('boom: E_TIMEOUT'); 1
    Wait For BiDi Log Entry    text=order-987    timeout=10
    ${orders}=    Get BiDi Console Log    text=order-987
    Should Not Be Empty    ${orders}
    ${codes}=     Get BiDi Console Log    pattern=E_[A-Z]+
    Should Not Be Empty    ${codes}
    ${err_orders}=    Get BiDi Console Log    level=error    text=boom
    Length Should Be    ${err_orders}    ${1}

Log BiDi Diagnostics On Demand
    [Documentation]    Diagnostics keyword (also usable as run_on_failure) returns state.
    Visit                       errors.html
    Wait For BiDi Log Entry     text=Intentional demo error    timeout=15
    ${diag}=    Log BiDi Diagnostics
    Should Be True              ${diag}[connected]
    Should Be True              len($diag['js_errors']) > 0
