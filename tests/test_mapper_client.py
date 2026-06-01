# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Unit tests for the driverless-Chrome mapper client (fake CDP transport).

Simulates Chrome's CDP socket + the chromium-bidi mapper's bindingCalled
responses, so the bootstrap + BiDi-over-CDP plumbing runs with no browser.
"""

import asyncio
import json

import pytest

from bidi_core.bidi_client import BiDiError
from bidi_core.mapper_client import MapperBiDiClient


class FakeCdpDuplex:
    """A CDP websocket fake that auto-answers bootstrap commands and emulates
    the mapper: when the client evaluates ``onBidiMessage(...)`` it pushes a
    ``Runtime.bindingCalled``/``sendBidiResponse`` success echoing the id."""

    def __init__(self):
        self.incoming = asyncio.Queue()
        self.closed = False
        self._cdp_results = {
            "Target.attachToBrowserTarget": {"sessionId": "BROWSER"},
            "Target.createTarget": {"targetId": "MAPPER_T"},
            "Target.attachToTarget": {"sessionId": "MAPPER_S"},
            "Runtime.enable": {},
            "Target.exposeDevToolsProtocol": {},
            "Runtime.addBinding": {},
        }

    async def send(self, data):
        msg = json.loads(data)
        method, mid = msg.get("method"), msg.get("id")
        if method == "Runtime.evaluate":
            expr = msg["params"]["expression"]
            self.incoming.put_nowait(json.dumps({"id": mid, "result": {"result": {"type": "undefined"}}}))
            if expr.startswith("onBidiMessage("):
                inner = json.loads(expr[len("onBidiMessage("):-1])  # JS string literal -> str
                cmd = json.loads(inner)  # -> BiDi command object
                payload = json.dumps({"type": "success", "id": cmd["id"], "result": {"echo": cmd["method"]}})
                self.incoming.put_nowait(json.dumps(
                    {"method": "Runtime.bindingCalled", "params": {"name": "sendBidiResponse", "payload": payload}}))
        elif mid is not None:
            self.incoming.put_nowait(json.dumps({"id": mid, "result": self._cdp_results.get(method, {})}))

    async def recv(self):
        if self.closed:
            raise ConnectionError("closed")
        return await self.incoming.get()

    async def close(self):
        self.closed = True

    def push_event(self, method, params):
        payload = json.dumps({"type": "event", "method": method, "params": params})
        self.incoming.put_nowait(json.dumps(
            {"method": "Runtime.bindingCalled", "params": {"name": "sendBidiResponse", "payload": payload}}))


async def _connect():
    fake = FakeCdpDuplex()
    client = MapperBiDiClient("ws://cdp", mapper_source="/* noop */", connector=lambda: _ret(fake))
    await client.connect()
    return client, fake


async def _ret(v):
    return v


@pytest.mark.asyncio
async def test_bootstrap_and_command_roundtrip():
    client, fake = await _connect()
    assert client._mapper_session == "MAPPER_S"
    result = await asyncio.wait_for(client.send_command("session.new", {"capabilities": {}}), 2)
    assert result == {"echo": "session.new"}
    await client.close()


@pytest.mark.asyncio
async def test_event_dispatch_via_binding():
    client, fake = await _connect()
    received = []
    client.add_event_listener("log.entryAdded", received.append)
    fake.push_event("log.entryAdded", {"text": "hi"})
    await asyncio.sleep(0.05)
    assert received == [{"text": "hi"}]
    await client.close()


@pytest.mark.asyncio
async def test_bidi_error_payload_raises():
    client, fake = await _connect()

    # Make the next onBidiMessage echo an error instead of success.
    async def send_error(data):
        msg = json.loads(data)
        if msg.get("method") == "Runtime.evaluate" and msg["params"]["expression"].startswith("onBidiMessage("):
            cmd = json.loads(json.loads(msg["params"]["expression"][len("onBidiMessage("):-1]))
            fake.incoming.put_nowait(json.dumps({"id": msg["id"], "result": {}}))
            fake.incoming.put_nowait(json.dumps({"method": "Runtime.bindingCalled", "params": {
                "name": "sendBidiResponse",
                "payload": json.dumps({"type": "error", "id": cmd["id"], "error": "no such frame", "message": "x"})}}))
        else:
            await FakeCdpDuplex.send(fake, data)

    fake.send = send_error
    with pytest.raises(BiDiError) as exc:
        await asyncio.wait_for(client.send_command("browsingContext.navigate", {}), 2)
    assert "no such frame" in str(exc.value)
    await client.close()
