# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Unit tests for page<->context correlation matching logic."""

from bidi_core.correlation import CorrelationCache, flatten_contexts, match_context

TREE = [
    {
        "context": "T-1",
        "url": "https://example.com/",
        "children": [
            {"context": "T-1-iframe", "url": "https://ads.example.com/", "children": []},
        ],
    },
    {"context": "T-2", "url": "https://other.com/", "children": []},
]


def test_match_by_target_id_preferred():
    assert match_context(TREE, target_id="T-2", url="https://example.com/") == "T-2"


def test_match_by_target_id_via_targetid_field():
    tree = [{"context": "ctx-9", "targetId": "TGT", "url": "x", "children": []}]
    assert match_context(tree, target_id="TGT") == "ctx-9"


def test_fallback_to_url_when_no_target_id():
    assert match_context(TREE, url="https://other.com/") == "T-2"


def test_fallback_first_in_creation_order():
    tree = [
        {"context": "A", "url": "https://dup.com/", "children": []},
        {"context": "B", "url": "https://dup.com/", "children": []},
    ]
    assert match_context(tree, url="https://dup.com/") == "A"


def test_flatten_includes_nested_children():
    ids = [c["context"] for c in flatten_contexts(TREE)]
    assert ids == ["T-1", "T-1-iframe", "T-2"]


def test_no_match_returns_none():
    assert match_context(TREE, target_id="nope", url="https://nowhere/") is None


def test_cache_put_get_invalidate():
    cache = CorrelationCache()
    cache.put("page-1", "ctx-1")
    assert cache.get("page-1") == "ctx-1"
    cache.invalidate("page-1")
    assert cache.get("page-1") is None
