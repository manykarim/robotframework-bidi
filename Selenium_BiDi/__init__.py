# Copyright 2026 MarketSquare
# Licensed under the Apache License, Version 2.0 (the "License").
"""Selenium-BiDi: a SeleniumLibrary adapter over :mod:`bidi_core`.

Loaded as a SeleniumLibrary plugin::

    Library    SeleniumLibrary    plugins=${path}/SeleniumBiDi.py

Brings the high-value WebDriver BiDi capabilities (network observe/mock, log,
user contexts, emulation, evaluate) to SeleniumLibrary suites over the same
framework-neutral engine the Browser adapter uses, with portable keyword names.
"""

__version__ = "0.2.0"
