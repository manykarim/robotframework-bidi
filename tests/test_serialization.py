# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Unit tests for BiDi structure normalization (headers, cookies, timings, RemoteValue)."""

from bidi_core.serialization import (
    compute_timing,
    headers_to_dict,
    normalize_cookie,
    remote_value_to_python,
)


def test_headers_to_dict_lowercases_and_unwraps():
    headers = [
        {"name": "Content-Type", "value": {"type": "string", "value": "text/html"}},
        {"name": "X-Cache", "value": {"type": "string", "value": "HIT"}},
    ]
    assert headers_to_dict(headers) == {"content-type": "text/html", "x-cache": "HIT"}


def test_headers_to_dict_handles_none():
    assert headers_to_dict(None) == {}


def test_normalize_cookie():
    c = normalize_cookie({
        "name": "sid", "value": {"type": "string", "value": "abc"},
        "domain": "example.com", "path": "/", "size": 6,
        "httpOnly": True, "secure": True, "sameSite": "strict",
    })
    assert c["name"] == "sid" and c["value"] == "abc"
    assert c["domain"] == "example.com" and c["httpOnly"] is True


def test_compute_timing_phases():
    t = compute_timing({
        "fetchStart": 0, "dnsStart": 1, "dnsEnd": 3,
        "connectStart": 3, "tlsStart": 5, "connectEnd": 10,
        "requestStart": 10, "responseStart": 20, "responseEnd": 30,
    })
    assert t["dns"] == 2
    assert t["connect"] == 7
    assert t["tls"] == 5            # connectEnd - tlsStart
    assert t["ttfb"] == 10          # responseStart - requestStart
    assert t["download"] == 10      # responseEnd - responseStart
    assert t["total"] == 30         # responseEnd - fetchStart


def test_compute_timing_zero_phases_are_none():
    t = compute_timing({"fetchStart": 0, "dnsStart": 0, "dnsEnd": 0, "responseEnd": 0})
    assert t["dns"] is None and t["total"] is None


def test_remote_value_primitives():
    assert remote_value_to_python({"type": "string", "value": "x"}) == "x"
    assert remote_value_to_python({"type": "number", "value": 42}) == 42
    assert remote_value_to_python({"type": "boolean", "value": True}) is True
    assert remote_value_to_python({"type": "null"}) is None
    assert remote_value_to_python({"type": "undefined"}) is None


def test_remote_value_array_and_object():
    arr = {"type": "array", "value": [{"type": "number", "value": 1}, {"type": "string", "value": "a"}]}
    assert remote_value_to_python(arr) == [1, "a"]
    obj = {"type": "object", "value": [["k", {"type": "number", "value": 2}]]}
    assert remote_value_to_python(obj) == {"k": 2}


def test_remote_value_node_summary():
    node = {"type": "node", "sharedId": "S1", "value": {
        "nodeType": 1, "localName": "div", "attributes": {"id": "main"}, "childNodeCount": 3,
    }}
    out = remote_value_to_python(node)
    assert out["sharedId"] == "S1" and out["localName"] == "div"
    assert out["attributes"] == {"id": "main"} and out["childNodeCount"] == 3
