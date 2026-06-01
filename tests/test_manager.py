# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Unit tests for BiDiManager using a fake client (no live browser)."""

import pytest

from bidi_core.bidi_client import BiDiClient, BiDiError
from bidi_core.manager import BiDiManager


class FakeClient(BiDiClient):
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.sent = []
        self.listeners = {}
        self.closed = False

    async def connect(self):
        return None

    async def send_command(self, method, params=None):
        self.sent.append((method, params or {}))
        value = self.responses.get(method, {})
        if isinstance(value, Exception):
            raise value
        return value

    def add_event_listener(self, method, callback):
        self.listeners.setdefault(method, []).append(callback)

    def remove_event_listener(self, method, callback):
        if callback in self.listeners.get(method, []):
            self.listeners[method].remove(callback)

    async def close(self):
        self.closed = True

    def emit(self, method, params):
        for cb in self.listeners.get(method, []):
            cb(params)


def make_manager(responses=None):
    fake = FakeClient(responses)
    manager = BiDiManager(client_factory=lambda url: fake, buffer_size=50)
    return manager, fake


def test_rejects_webkit_before_connecting():
    manager, _ = make_manager()
    with pytest.raises(BiDiError) as exc:
        manager.connect("ws://x", browser="webkit")
    assert "not available" in str(exc.value)


def test_connect_runs_session_new_then_disconnect():
    manager, fake = make_manager()
    manager.connect("ws://x", browser="chromium")
    assert ("session.new", {"capabilities": {}}) in fake.sent
    manager.disconnect()
    assert fake.closed is True


def test_auto_subscribe_on_connect():
    manager, fake = make_manager()
    manager.connect("ws://x", auto_subscribe=["log.entryAdded"])
    methods = [m for m, _ in fake.sent]
    assert "session.subscribe" in methods
    manager.disconnect()


def test_network_events_filtered_by_glob():
    manager, fake = make_manager()
    manager.connect("ws://x")
    fake.emit("network.responseCompleted", {"request": {"request": "1", "url": "https://api/x"}})
    fake.emit("network.responseCompleted", {"request": {"request": "2", "url": "https://cdn/y.js"}})
    api = manager.get_network_events(url_glob="https://api/*")
    assert [e["request"]["request"] for e in api] == ["1"]
    manager.disconnect()


def test_get_response_body_unwraps_value():
    manager, fake = make_manager(
        {"network.getData": {"bytes": {"type": "string", "value": "hello"}}}
    )
    manager.connect("ws://x")
    assert manager.get_response_body("req-1") == "hello"
    manager.disconnect()


def test_get_response_body_unknown_id_raises_actionable():
    manager, fake = make_manager({"network.getData": BiDiError("no such request")})
    manager.connect("ws://x")
    with pytest.raises(BiDiError) as exc:
        manager.get_response_body("missing")
    assert "No retrievable response body" in str(exc.value)
    manager.disconnect()


def test_js_errors_filter():
    manager, fake = make_manager()
    manager.connect("ws://x")
    fake.emit("log.entryAdded", {"type": "console", "level": "info", "text": "ok"})
    fake.emit("log.entryAdded", {"type": "javascript", "level": "error", "text": "boom"})
    errors = manager.get_js_errors()
    assert [e["text"] for e in errors] == ["boom"]
    manager.disconnect()


def test_evaluate_requires_target():
    manager, fake = make_manager()
    manager.connect("ws://x")
    with pytest.raises(BiDiError):
        manager.evaluate("1+1")
    manager.disconnect()


def test_evaluate_returns_value_for_context():
    manager, fake = make_manager(
        {"script.evaluate": {"type": "success", "result": {"type": "number", "value": 2}}}
    )
    manager.connect("ws://x")
    assert manager.evaluate("1+1", context="ctx-1") == 2
    manager.disconnect()


def test_evaluate_surfaces_exception():
    manager, fake = make_manager(
        {"script.evaluate": {"type": "exception", "exceptionDetails": {"text": "ReferenceError"}}}
    )
    manager.connect("ws://x")
    with pytest.raises(BiDiError) as exc:
        manager.evaluate("nope()", context="ctx-1")
    assert "ReferenceError" in str(exc.value)
    manager.disconnect()


def test_wait_for_response_returns_buffered_match():
    manager, fake = make_manager()
    manager.connect("ws://x")
    fake.emit("network.responseCompleted", {"request": {"request": "1", "url": "https://api/profile"}})
    event = manager.wait_for_response("https://api/*", timeout=1)
    assert event["request"]["request"] == "1"
    manager.disconnect()


def test_get_response_status_and_headers():
    manager, fake = make_manager()
    manager.connect("ws://x")
    fake.emit("network.responseCompleted", {
        "request": {"request": "1", "url": "https://api/x"},
        "response": {"status": 200, "headers": [
            {"name": "Content-Type", "value": {"type": "string", "value": "application/json"}}]},
    })
    assert manager.get_response_status("https://api/*") == 200
    assert manager.get_response_headers("https://api/*") == {"content-type": "application/json"}
    manager.disconnect()


def test_get_response_status_no_match_raises():
    manager, fake = make_manager()
    manager.connect("ws://x")
    with pytest.raises(BiDiError):
        manager.get_response_status("https://nope/*")
    manager.disconnect()


def test_network_event_count_and_resource_timings():
    manager, fake = make_manager()
    manager.connect("ws://x")
    fake.emit("network.responseCompleted", {
        "request": {"request": "1", "url": "https://api/x",
                    "timings": {"fetchStart": 0, "requestStart": 5, "responseStart": 15, "responseEnd": 25}},
        "response": {"status": 200, "headers": []},
    })
    assert manager.get_network_event_count(url_glob="https://api/*") == 1
    timings = manager.get_resource_timings(url_glob="https://api/*")
    assert timings[0]["url"] == "https://api/x"
    assert timings[0]["ttfb"] == 10 and timings[0]["total"] == 25
    manager.disconnect()


def test_log_counts():
    manager, fake = make_manager()
    manager.connect("ws://x")
    fake.emit("log.entryAdded", {"type": "console", "level": "info", "text": "a"})
    fake.emit("log.entryAdded", {"type": "javascript", "level": "error", "text": "boom"})
    assert manager.get_console_log_count() == 2
    assert manager.get_console_log_count(level="error") == 1
    assert manager.get_js_error_count() == 1
    manager.disconnect()


def test_get_cookies_normalized_and_filtered():
    manager, fake = make_manager({"storage.getCookies": {"cookies": [
        {"name": "sid", "value": {"type": "string", "value": "abc"}, "domain": "ex.com",
         "path": "/", "size": 6, "httpOnly": True, "secure": True, "sameSite": "strict"}]}})
    manager.connect("ws://x")
    cookies = manager.get_cookies(name="sid")
    assert cookies == [{"name": "sid", "value": "abc", "domain": "ex.com", "path": "/",
                        "size": 6, "httpOnly": True, "secure": True, "sameSite": "strict", "expiry": None}]
    manager.disconnect()


def test_locate_nodes_and_element_count():
    manager, fake = make_manager({
        "browsingContext.getTree": {"contexts": [{"context": "C1", "url": "u"}]},
        "browsingContext.locateNodes": {"nodes": [
            {"type": "node", "sharedId": "n1", "value": {"nodeType": 1, "localName": "h1"}},
            {"type": "node", "sharedId": "n2", "value": {"nodeType": 1, "localName": "h1"}}]},
    })
    manager.connect("ws://x")
    nodes = manager.locate_nodes("css", "h1")
    assert [n["localName"] for n in nodes] == ["h1", "h1"]
    assert manager.get_element_count("css", "h1") == 2
    # verify the css locator shape was sent
    assert any(m == "browsingContext.locateNodes" and p["locator"] == {"type": "css", "value": "h1"}
               for m, p in fake.sent)
    manager.disconnect()


def test_locator_strategies_build_correctly():
    assert BiDiManager._build_locator("xpath", "//h1") == {"type": "xpath", "value": "//h1"}
    assert BiDiManager._build_locator("text", "Hi") == {"type": "innerText", "value": "Hi"}
    acc = BiDiManager._build_locator("accessibility", "role=button;name=Save")
    assert acc == {"type": "accessibility", "value": {"role": "button", "name": "Save"}}


def test_clear_buffers_resets_counts():
    manager, fake = make_manager()
    manager.connect("ws://x")
    fake.emit("log.entryAdded", {"type": "console", "level": "info", "text": "a"})
    fake.emit("network.responseCompleted", {"request": {"request": "1", "url": "u"}})
    assert manager.get_console_log_count() == 1
    manager.clear_buffers()
    assert manager.get_console_log_count() == 0
    assert manager.get_network_event_count() == 0
    manager.disconnect()


def test_get_contexts_flattens_tree():
    manager, fake = make_manager({"browsingContext.getTree": {"contexts": [
        {"context": "TOP", "url": "https://a/", "children": [
            {"context": "FRAME", "url": "https://a/frame", "children": []}]}]}})
    manager.connect("ws://x")
    contexts = manager.get_contexts()
    assert [c["context"] for c in contexts] == ["TOP", "FRAME"]
    assert contexts[1]["url"] == "https://a/frame"
    manager.disconnect()


def test_get_url_and_title_via_evaluate():
    manager, fake = make_manager({
        "browsingContext.getTree": {"contexts": [{"context": "C1", "url": "u"}]},
        "script.evaluate": {"type": "success", "result": {"type": "string", "value": "https://a/"}},
    })
    manager.connect("ws://x")
    assert manager.get_url() == "https://a/"
    manager.disconnect()


def test_context_for_page_caches_stable_target_id():
    manager, fake = make_manager(
        {"browsingContext.getTree": {"contexts": [{"context": "C1", "targetId": "T1"}]}}
    )
    manager.connect("ws://x")
    assert manager.context_for_page(target_id="T1") == "C1"
    # Target id is stable -> served from cache even if the tree is now empty.
    fake.responses["browsingContext.getTree"] = {"contexts": []}
    assert manager.context_for_page(target_id="T1") == "C1"
    manager.disconnect()


def test_url_only_correlation_is_recomputed_each_call():
    manager, fake = make_manager(
        {"browsingContext.getTree": {"contexts": [{"context": "C1", "url": "https://a/"}]}}
    )
    manager.connect("ws://x")
    assert manager.context_for_page(url="https://a/") == "C1"
    # No target id -> not cached -> fresh tree wins (inherent nav refresh).
    fake.responses["browsingContext.getTree"] = {"contexts": [{"context": "C2", "url": "https://b/"}]}
    assert manager.context_for_page(url="https://b/") == "C2"
    manager.disconnect()


# -- network interception ------------------------------------------------

def _block(url, rid="r1"):
    return {"isBlocked": True, "request": {"request": rid, "url": url}}


def test_mock_response_answers_with_provide():
    manager, fake = make_manager()
    manager.connect("ws://x")
    manager.add_mock("https://api/*", status=201, body='{"ok":1}', headers={"X-Test": "1"})
    fake.emit("network.beforeRequestSent", _block("https://api/data"))
    sent = dict((m, p) for m, p in fake.sent)
    assert "network.provideResponse" in sent
    p = sent["network.provideResponse"]
    assert p["request"] == "r1" and p["statusCode"] == 201
    assert p["body"] == {"type": "string", "value": '{"ok":1}'}
    assert any(h["name"] == "X-Test" for h in p["headers"])
    manager.disconnect()


def test_fault_answers_with_fail():
    manager, fake = make_manager()
    manager.connect("ws://x")
    manager.add_fault("*/flaky")
    fake.emit("network.beforeRequestSent", _block("https://x/flaky"))
    assert "network.failRequest" in [m for m, _ in fake.sent]
    manager.disconnect()


def test_non_matching_blocked_request_is_continued():
    manager, fake = make_manager()
    manager.connect("ws://x")
    manager.add_mock("https://api/*")  # installs intercept
    fake.emit("network.beforeRequestSent", _block("https://other/page"))  # no action matches
    assert "network.continueRequest" in [m for m, _ in fake.sent]
    manager.disconnect()


def test_header_injection_continues_with_headers():
    manager, fake = make_manager()
    manager.connect("ws://x")
    manager.add_header_injection("*/api/*", {"Authorization": "Bearer t"})
    fake.emit("network.beforeRequestSent", _block("https://h/api/x"))
    sent = dict((m, p) for m, p in fake.sent)
    assert any(h["name"] == "Authorization" for h in sent["network.continueRequest"]["headers"])
    manager.disconnect()


def test_auth_provides_credentials():
    manager, fake = make_manager()
    manager.connect("ws://x")
    manager.add_auth("*/secure", "u", "p")
    fake.emit("network.authRequired", _block("https://s/secure"))
    sent = dict((m, p) for m, p in fake.sent)
    assert sent["network.continueWithAuth"]["action"] == "provideCredentials"
    assert sent["network.continueWithAuth"]["credentials"]["username"] == "u"
    manager.disconnect()


def test_response_timing_phase():
    manager, fake = make_manager()
    manager.connect("ws://x")
    fake.emit("network.responseCompleted", {"request": {"request": "1", "url": "https://api/x",
        "timings": {"fetchStart": 0, "requestStart": 5, "responseStart": 20, "responseEnd": 30}}})
    assert manager.get_response_timing("https://api/*", "ttfb") == 15
    assert manager.get_response_timing("https://api/*", "total") == 30
    manager.disconnect()


# -- emulation & user contexts -------------------------------------------

def test_emulation_overrides_send_commands():
    manager, fake = make_manager()
    manager.connect("ws://x")
    manager.set_geolocation(48.2, 16.3, context="C1")
    manager.set_locale("de-DE", context="C1")
    manager.set_timezone("Europe/Berlin", context="C1")
    manager.set_forced_colors("dark", context="C1")
    sent = {m: p for m, p in fake.sent}
    assert sent["emulation.setGeolocationOverride"]["coordinates"]["latitude"] == 48.2
    assert sent["emulation.setGeolocationOverride"]["contexts"] == ["C1"]
    assert sent["emulation.setLocaleOverride"]["locale"] == "de-DE"
    assert sent["emulation.setTimezoneOverride"]["timezone"] == "Europe/Berlin"
    assert sent["emulation.setForcedColorsModeThemeOverride"]["theme"] == "dark"
    manager.disconnect()


def test_set_viewport_resolves_context():
    manager, fake = make_manager({"browsingContext.getTree": {"contexts": [{"context": "C1", "url": "u"}]}})
    manager.connect("ws://x")
    manager.set_viewport(800, 600)
    sent = {m: p for m, p in fake.sent}
    assert sent["browsingContext.setViewport"]["viewport"] == {"width": 800, "height": 600}
    manager.disconnect()


def test_user_context_lifecycle_and_teardown():
    manager, fake = make_manager({"browser.createUserContext": {"userContext": "uc1"},
                                  "browsingContext.create": {"context": "ctx-in-uc"}})
    manager.connect("ws://x")
    uc = manager.create_user_context()
    assert uc == "uc1" and "uc1" in manager._user_contexts
    new_ctx = manager.create_context(user_context=uc)
    assert new_ctx == "ctx-in-uc"
    sent = {m: p for m, p in fake.sent}
    assert sent["browsingContext.create"]["userContext"] == "uc1"
    manager.disconnect()  # should remove uc1
    assert ("browser.removeUserContext", {"userContext": "uc1"}) in fake.sent


# -- input, storage writes, navigation, downloads ------------------------

def test_set_cookie_and_delete():
    manager, fake = make_manager()
    manager.connect("ws://x")
    manager.set_cookie("sid", "abc", "example.com", secure=True, http_only=True)
    manager.delete_cookies(name="sid", domain="example.com")
    sent = {m: p for m, p in fake.sent}
    c = sent["storage.setCookie"]["cookie"]
    assert c["name"] == "sid" and c["value"] == {"type": "string", "value": "abc"}
    assert c["secure"] is True and c["domain"] == "example.com"
    assert sent["storage.deleteCookies"]["filter"] == {"name": "sid", "domain": "example.com"}
    manager.disconnect()


def test_wheel_scroll_builds_action_source():
    manager, fake = make_manager({"browsingContext.getTree": {"contexts": [{"context": "C1", "url": "u"}]}})
    manager.connect("ws://x")
    manager.wheel_scroll(0, 240, x=10, y=20)
    sent = {m: p for m, p in fake.sent}
    src = sent["input.performActions"]["actions"][0]
    assert src["type"] == "wheel" and src["actions"][0]["deltaY"] == 240
    manager.disconnect()


def test_set_files_locates_then_sets():
    manager, fake = make_manager({
        "browsingContext.getTree": {"contexts": [{"context": "C1", "url": "u"}]},
        "browsingContext.locateNodes": {"nodes": [{"type": "node", "sharedId": "s1", "value": {"localName": "input"}}]}})
    manager.connect("ws://x")
    manager.set_files("css", "#upload", ["/tmp/a.txt"])
    sent = {m: p for m, p in fake.sent}
    assert sent["input.setFiles"]["element"] == {"sharedId": "s1"}
    assert sent["input.setFiles"]["files"] == ["/tmp/a.txt"]
    manager.disconnect()


def test_navigation_event_buffering_and_wait():
    manager, fake = make_manager()
    manager.connect("ws://x", auto_subscribe=["browsingContext.load"])
    fake.emit("browsingContext.load", {"context": "C1", "url": "https://a/", "timestamp": 1})
    evts = manager.get_navigation_events("load")
    assert evts and evts[-1]["url"] == "https://a/"
    # wait returns the buffered/next one
    got = manager.wait_for_navigation("load", context="C1", timeout=1)
    assert got["context"] == "C1"
    manager.disconnect()


def test_set_download_behavior():
    manager, fake = make_manager()
    manager.connect("ws://x")
    manager.set_download_behavior(destination_folder="/tmp/dl")
    sent = {m: p for m, p in fake.sent}
    assert sent["browser.setDownloadBehavior"]["downloadBehavior"]["destinationFolder"] == "/tmp/dl"
    manager.disconnect()


# -- performance analysis & console search -------------------------------

def _resp(rid, url, total_ms, size):
    return {"request": {"request": rid, "url": url,
            "timings": {"fetchStart": 0, "requestStart": 0, "responseStart": 0, "responseEnd": total_ms}},
            "response": {"status": 200, "bytesReceived": size, "headers": []}}


def test_slowest_resources_sorted_and_limited():
    manager, fake = make_manager()
    manager.connect("ws://x")
    fake.emit("network.responseCompleted", _resp("1", "https://a/fast.js", 10, 100))
    fake.emit("network.responseCompleted", _resp("2", "https://a/slow.js", 500, 200))
    fake.emit("network.responseCompleted", _resp("3", "https://a/mid.js", 100, 9000))
    slow = manager.get_slowest_resources(top=2)
    assert [e["url"] for e in slow] == ["https://a/slow.js", "https://a/mid.js"]
    assert slow[0]["total"] == 500
    manager.disconnect()


def test_largest_resources_by_size():
    manager, fake = make_manager()
    manager.connect("ws://x")
    fake.emit("network.responseCompleted", _resp("1", "https://a/small", 10, 100))
    fake.emit("network.responseCompleted", _resp("2", "https://a/big", 20, 9000))
    big = manager.get_largest_resources(top=1)
    assert big[0]["url"] == "https://a/big" and big[0]["size"] == 9000
    manager.disconnect()


def test_resource_timings_bad_sort_raises():
    manager, fake = make_manager()
    manager.connect("ws://x")
    with pytest.raises(BiDiError):
        manager.get_resource_timings(sort_by="nonsense")
    manager.disconnect()


def test_console_log_text_and_pattern_filters():
    manager, fake = make_manager()
    manager.connect("ws://x")
    fake.emit("log.entryAdded", {"level": "info", "text": "Checkout started"})
    fake.emit("log.entryAdded", {"level": "error", "text": "Payment failed: code 42"})
    fake.emit("log.entryAdded", {"level": "info", "text": "render ok"})
    assert [e["text"] for e in manager.get_console_log(text="checkout")] == ["Checkout started"]
    assert [e["text"] for e in manager.get_console_log(pattern=r"code \d+")] == ["Payment failed: code 42"]
    assert [e["text"] for e in manager.get_console_log(level="error", text="payment")] == ["Payment failed: code 42"]
    manager.disconnect()
