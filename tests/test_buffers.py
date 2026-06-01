# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Unit tests for bounded event buffers (since-markers + observable overflow)."""

from bidi_core.buffers import EventBuffer, EventBuffers


def test_since_marker_returns_only_newer():
    buf = EventBuffer(maxlen=10)
    buf.append({"n": 1})
    marker = buf.latest_seq()
    buf.append({"n": 2})
    buf.append({"n": 3})
    assert buf.get(since=marker) == [{"n": 2}, {"n": 3}]


def test_predicate_filters():
    buf = EventBuffer(maxlen=10)
    for level in ("info", "error", "info", "error"):
        buf.append({"level": level})
    errors = buf.get(predicate=lambda e: e["level"] == "error")
    assert errors == [{"level": "error"}, {"level": "error"}]


def test_overflow_drops_oldest_and_is_observable():
    buf = EventBuffer(maxlen=3)
    for n in range(5):
        buf.append({"n": n})
    remaining = [e["n"] for e in buf.get()]
    assert remaining == [2, 3, 4]
    assert buf.dropped == 2


def test_event_buffers_lazily_create_and_track_dropped():
    buffers = EventBuffers(maxlen=2)
    for n in range(3):
        buffers.append("log.entryAdded", {"n": n})
    buffers.append("network.responseCompleted", {"x": 1})
    assert [e["n"] for e in buffers.buffer("log.entryAdded").get()] == [1, 2]
    assert buffers.dropped_total == 1
