# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Unit tests for the background asyncio loop runner."""

import asyncio

import pytest

from bidi_core.loop_runner import LoopRunner


def test_runs_coroutine_and_returns_result():
    runner = LoopRunner()
    runner.start()
    try:
        async def coro():
            await asyncio.sleep(0)
            return 42

        assert runner.run(coro()) == 42
    finally:
        runner.stop()


def test_run_before_start_raises():
    runner = LoopRunner()

    async def coro():
        return 1

    c = coro()
    with pytest.raises(RuntimeError):
        runner.run(c)
    c.close()  # avoid "coroutine never awaited" warning


def test_stop_is_idempotent():
    runner = LoopRunner()
    runner.start()
    runner.stop()
    runner.stop()  # must not raise
    assert runner.running is False
