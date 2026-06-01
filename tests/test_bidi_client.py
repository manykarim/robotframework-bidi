# Copyright 2026 MarketSquare
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Unit tests for the thin BiDi client: id->future correlation + event dispatch.

Uses an in-memory fake duplex so the client logic runs with no browser.
"""

import asyncio
import json

import pytest

from bidi_core.bidi_client import BiDiError, WebsocketsBiDiClient


class FakeDuplex:
    """A websocket-like duplex backed by asyncio queues, with a scripted server."""

    def __init__(self):
        self.outgoing = asyncio.Queue()  # messages the client sends
        self.incoming = asyncio.Queue()  # messages the client will recv
        self.closed = False

    async def send(self, data):
        await self.outgoing.put(json.loads(data))

    async def recv(self):
        if self.closed:
            raise ConnectionError("closed")
        return await self.incoming.get()

    async def close(self):
        self.closed = True

    def push(self, message):
        self.incoming.put_nowait(json.dumps(message))


async def _connect_with_fake():
    fake = FakeDuplex()

    async def connector():
        return fake

    client = WebsocketsBiDiClient("ws://test", connector=connector)
    await client.connect()
    return client, fake


@pytest.mark.asyncio
async def test_command_resolves_matching_id():
    client, fake = await _connect_with_fake()
    task = asyncio.ensure_future(client.send_command("session.status"))
    sent = await fake.outgoing.get()
    assert sent["method"] == "session.status"
    fake.push({"id": sent["id"], "type": "success", "result": {"ready": True}})
    result = await asyncio.wait_for(task, 1)
    assert result == {"ready": True}
    await client.close()


@pytest.mark.asyncio
async def test_error_response_raises():
    client, fake = await _connect_with_fake()
    task = asyncio.ensure_future(client.send_command("network.getData", {"request": "x"}))
    sent = await fake.outgoing.get()
    fake.push({"id": sent["id"], "type": "error", "error": "no such request", "message": "x"})
    with pytest.raises(BiDiError) as exc:
        await asyncio.wait_for(task, 1)
    assert "no such request" in str(exc.value)
    await client.close()


@pytest.mark.asyncio
async def test_cdp_style_error_is_detected():
    # Chrome's CDP endpoint (not BiDi) returns {"id","error":{"code","message"}}.
    client, fake = await _connect_with_fake()
    task = asyncio.ensure_future(client.send_command("session.new"))
    sent = await fake.outgoing.get()
    fake.push({"id": sent["id"], "error": {"code": -32601, "message": "'session.new' wasn't found"}})
    with pytest.raises(BiDiError) as exc:
        await asyncio.wait_for(task, 1)
    assert "wasn't found" in str(exc.value)
    await client.close()


@pytest.mark.asyncio
async def test_concurrent_commands_correlate_independently():
    client, fake = await _connect_with_fake()
    t1 = asyncio.ensure_future(client.send_command("a"))
    t2 = asyncio.ensure_future(client.send_command("b"))
    s1 = await fake.outgoing.get()
    s2 = await fake.outgoing.get()
    # Reply out of order: b first, then a.
    fake.push({"id": s2["id"], "type": "success", "result": {"who": "b"}})
    fake.push({"id": s1["id"], "type": "success", "result": {"who": "a"}})
    assert (await asyncio.wait_for(t1, 1)) == {"who": "a"}
    assert (await asyncio.wait_for(t2, 1)) == {"who": "b"}
    await client.close()


@pytest.mark.asyncio
async def test_events_dispatched_to_listeners():
    client, fake = await _connect_with_fake()
    received = []
    client.add_event_listener("log.entryAdded", received.append)
    fake.push({"type": "event", "method": "log.entryAdded", "params": {"text": "hi"}})
    await asyncio.sleep(0.05)
    assert received == [{"text": "hi"}]
    await client.close()


@pytest.mark.asyncio
async def test_remove_listener_stops_delivery():
    client, fake = await _connect_with_fake()
    received = []
    cb = received.append
    client.add_event_listener("log.entryAdded", cb)
    client.remove_event_listener("log.entryAdded", cb)
    fake.push({"type": "event", "method": "log.entryAdded", "params": {"text": "hi"}})
    await asyncio.sleep(0.05)
    assert received == []
    await client.close()


@pytest.mark.asyncio
async def test_close_fails_pending_commands():
    client, fake = await _connect_with_fake()
    task = asyncio.ensure_future(client.send_command("session.status"))
    await fake.outgoing.get()
    await client.close()
    with pytest.raises(BiDiError):
        await asyncio.wait_for(task, 1)
