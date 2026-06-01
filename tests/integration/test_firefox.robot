*** Settings ***
Documentation    Firefox: DOCUMENTED LIMITATION (validated 2026-05-29, see spike/RESULTS.md).
...
...              Full Strategy-1 coexistence is NOT achievable through the Browser library
...              on Firefox: Firefox has no CDP, and Browser/Playwright cannot attach to an
...              externally launched Firefox -- it launches its OWN. So a BiDi session (on a
...              geckodriver-launched Firefox) and Playwright's `New Page` end up on DIFFERENT
...              Firefox instances and cannot share contexts or logs.
...
...              Firefox is therefore supported at the BiDi-client level only; that path is
...              validated by `spike/run_firefox.py` (6/6: connect, subscribe, network events,
...              console log, URL-based correlation, BiDi Evaluate). Response bodies are
...              unreliable on Firefox (network.getData fails on compressed streams).
...
...              These cases are skipped until Browser/Playwright can drive an external Firefox.
Force Tags       firefox    known-limitation    skip

*** Test Cases ***
Firefox Full-Stack Coexistence Not Supported
    [Documentation]    Placeholder documenting the limitation; see spike/run_firefox.py
    ...                for the validated BiDi-client-level Firefox coverage.
    Skip    Firefox full Strategy-1 via Browser is not achievable; use spike/run_firefox.py.
