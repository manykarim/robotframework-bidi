# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
"""Normalize BiDi protocol structures into plain, assertable Python values.

Pure functions (protocol-in, python-out) so they unit-test without a browser.
Covers BiDi ``RemoteValue``, network header/cookie shapes, and FetchTimingInfo.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def header_value(entry: Dict[str, Any]) -> str:
    """A BiDi header/cookie value is ``{type, value}`` (or base64). Return text."""
    v = entry.get("value")
    if isinstance(v, dict):
        return v.get("value", "")
    return "" if v is None else str(v)


def headers_to_dict(headers: Optional[List[Dict[str, Any]]]) -> Dict[str, str]:
    """BiDi ``[{name, value:{type,value}}, ...]`` -> ``{name: value}``.

    Header names are matched case-insensitively by lower-casing keys.
    """
    result: Dict[str, str] = {}
    for h in headers or []:
        name = h.get("name")
        if name is not None:
            result[name.lower()] = header_value(h)
    return result


def normalize_cookie(cookie: Dict[str, Any]) -> Dict[str, Any]:
    """BiDi cookie -> flat dict with a plain string ``value``."""
    return {
        "name": cookie.get("name"),
        "value": header_value(cookie),
        "domain": cookie.get("domain"),
        "path": cookie.get("path"),
        "size": cookie.get("size"),
        "httpOnly": cookie.get("httpOnly"),
        "secure": cookie.get("secure"),
        "sameSite": cookie.get("sameSite"),
        "expiry": cookie.get("expiry"),
    }


def compute_timing(timings: Optional[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """FetchTimingInfo (ms offsets from timeOrigin) -> QA-relevant phase durations.

    Returns dns / connect / tls / ttfb / download / total in milliseconds. Phases
    that the browser reports as 0 (not applicable, e.g. cached) come back as None.
    """
    t = timings or {}

    def span(start_key: str, end_key: str) -> Optional[float]:
        start = t.get(start_key) or 0
        end = t.get(end_key) or 0
        if not start or not end or end < start:
            return None
        return round(end - start, 3)

    fetch_start = t.get("fetchStart") or 0
    response_end = t.get("responseEnd") or 0
    request_start = t.get("requestStart") or 0
    response_start = t.get("responseStart") or 0
    return {
        "dns": span("dnsStart", "dnsEnd"),
        "connect": span("connectStart", "connectEnd"),
        "tls": (round((t.get("connectEnd") or 0) - t["tlsStart"], 3)
                if t.get("tlsStart") and t.get("connectEnd") else None),
        "ttfb": (round(response_start - request_start, 3)
                 if response_start and request_start and response_start >= request_start else None),
        "download": (round(response_end - response_start, 3)
                     if response_end and response_start and response_end >= response_start else None),
        "total": (round(response_end - fetch_start, 3)
                  if response_end and response_end >= fetch_start else None),
    }


def to_bidi_headers(headers: Optional[Dict[str, str]]) -> List[Dict[str, Any]]:
    """``{name: value}`` -> BiDi header list ``[{name, value:{type,value}}]``."""
    return [
        {"name": str(name), "value": {"type": "string", "value": str(value)}}
        for name, value in (headers or {}).items()
    ]


def to_bidi_body(body: Optional[str]) -> Optional[Dict[str, Any]]:
    """Wrap a text body as a BiDi ``BytesValue`` (``{type:"string", value}``)."""
    if body is None:
        return None
    return {"type": "string", "value": body}


def remote_value_to_python(rv: Any) -> Any:
    """Recursively convert a BiDi ``RemoteValue`` to a plain Python value.

    Primitives unwrap to their value; arrays/objects/maps recurse; DOM nodes
    become a compact summary dict (so they are assertable and serialisable).
    """
    if not isinstance(rv, dict):
        return rv
    t = rv.get("type")
    if t in ("string", "boolean"):
        return rv.get("value")
    if t == "number":
        val = rv.get("value")
        if val in ("Infinity", "-Infinity", "NaN"):
            return val
        return val
    if t in ("null", "undefined"):
        return None
    if t == "bigint":
        return rv.get("value")
    if t == "array" or t == "set":
        return [remote_value_to_python(item) for item in rv.get("value", [])]
    if t == "object" or t == "map":
        out: Dict[Any, Any] = {}
        for pair in rv.get("value", []):
            if isinstance(pair, list) and len(pair) == 2:
                key = pair[0]
                key = key.get("value") if isinstance(key, dict) else key
                out[key] = remote_value_to_python(pair[1])
        return out
    if t == "node":
        node = rv.get("value", {}) or {}
        attrs = node.get("attributes", {}) or {}
        return {
            "sharedId": rv.get("sharedId"),
            "nodeType": node.get("nodeType"),
            "localName": node.get("localName"),
            "namespaceURI": node.get("namespaceURI"),
            "attributes": attrs,
            "childNodeCount": node.get("childNodeCount"),
            "nodeValue": node.get("nodeValue"),
        }
    # Fallback: return the raw value if present, else the descriptor.
    return rv.get("value", rv)
