"""Inter-actor transport — THE SINGLE SWAP POINT for A2A vs local HTTP.

Environment A (runs now): `HttpLocalTransport` speaks the SAME A2A v1.0 JSON-RPC
`SendMessage` envelope (data part carrying the structured payload) over localhost
HTTP between three separate OS processes. This is the "暫定 HTTP" path the work
order permits, used here because the real A2A plugin needs a running Hermes model
runtime (environment B).

Environment B: `HermesA2ATransport` posts the identical envelope to a real Hermes
instance's A2A port with bearer auth, per docs/a2a-facts.md (§2, §3). It is real,
usable code; it is simply not exercised in environment A.

Select with env var `A2A_ECONOMY_TRANSPORT` (`http-local` default, or `hermes-a2a`).
This is the ONE place the transport is chosen — nothing else in the codebase
imports urllib or knows the wire format.

Envelope shape is faithful to the real plugin:
  request : {"jsonrpc":"2.0","id":"task-..","method":"SendMessage",
             "params":{"message":{"role":"ROLE_USER","parts":[{"data":{...}}],
                                  "messageId":"..","contextId":".."}}}
  reply   : {"jsonrpc":"2.0","id":..,"result":{"task":{"id":..,"contextId":..,
             "status":{"state":"COMPLETED","message":{"role":"ROLE_AGENT",
                       "parts":[{"data":{...}}]}}}}}
(protocol.py:261-282, :367-396; adapter.py:137-160, :954)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any

PROTOCOL_VERSION = "1.0"
ROLE_USER = "ROLE_USER"
ROLE_AGENT = "ROLE_AGENT"
STATE_COMPLETED = "COMPLETED"
STATE_REJECTED = "REJECTED"


def new_task_id() -> str:
    return "task-" + uuid.uuid4().hex[:16]


def new_context_id() -> str:
    return "ctx-" + uuid.uuid4().hex[:16]


def _message(role: str, data: dict[str, Any], context_id: str | None) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "role": role,
        "parts": [{"data": data}],
        "messageId": uuid.uuid4().hex,
    }
    if context_id:
        msg["contextId"] = context_id
    return msg


def build_request(data: dict[str, Any], context_id: str | None) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": new_task_id(),
        "method": "SendMessage",
        "params": {"message": _message(ROLE_USER, data, context_id)},
    }


def build_reply(req_id: str, data: dict[str, Any], context_id: str | None,
                state: str = STATE_COMPLETED) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "task": {
                "id": req_id,
                "contextId": context_id or new_context_id(),
                "status": {
                    "state": state,
                    "message": _message(ROLE_AGENT, data, context_id),
                },
            }
        },
    }


def extract_data(envelope: dict[str, Any]) -> dict[str, Any]:
    """Pull the structured data part out of a request or reply envelope.

    Fails loudly (KeyError/ValueError) on a shape it does not understand rather
    than returning a silent empty dict.
    """
    if "params" in envelope:  # request
        message = envelope["params"]["message"]
    elif "result" in envelope:  # reply
        message = envelope["result"]["task"]["status"]["message"]
    else:
        raise ValueError(f"unrecognized envelope (no params/result): {list(envelope)}")
    for part in message["parts"]:
        if "data" in part:
            return part["data"]
    raise ValueError("envelope message has no data part")


def reply_state(envelope: dict[str, Any]) -> str:
    return envelope["result"]["task"]["status"]["state"]


class HttpLocalTransport:
    """Environment-A transport: JSON-RPC SendMessage over localhost HTTP."""

    name = "http-local"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def call(self, peer_url: str, data: dict[str, Any], context_id: str | None,
             token: str | None = None) -> dict[str, Any]:
        req_env = build_request(data, context_id)
        body = json.dumps(req_env).encode("utf-8")
        headers = {"Content-Type": "application/json", "A2A-Version": PROTOCOL_VERSION}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(peer_url, data=body, headers=headers, method="POST")
        # No retry — matches A2A (docs/a2a-facts.md §6). Errors propagate.
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            reply = json.loads(resp.read().decode("utf-8"))
        return reply


class HermesA2ATransport:
    """Environment-B transport: post the same envelope to a real Hermes A2A port.

    Wired per docs/a2a-facts.md: peer URL is the agent's A2A endpoint (POST /),
    bearer token from A2A_PEER_TOKENS. Not exercised in environment A; requires a
    running Hermes runtime. It raises on any transport error (never swallows).
    """

    name = "hermes-a2a"

    def __init__(self, timeout: float = 120.0) -> None:
        self.timeout = timeout

    def call(self, peer_url: str, data: dict[str, Any], context_id: str | None,
             token: str | None = None) -> dict[str, Any]:
        # Identical envelope; the real plugin accepts data parts (protocol.py:256).
        req_env = build_request(data, context_id)
        body = json.dumps(req_env).encode("utf-8")
        headers = {"Content-Type": "application/json", "A2A-Version": PROTOCOL_VERSION}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(peer_url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


def get_transport() -> Any:
    choice = os.getenv("A2A_ECONOMY_TRANSPORT", "http-local")
    if choice == "http-local":
        return HttpLocalTransport()
    if choice == "hermes-a2a":
        return HermesA2ATransport()
    raise ValueError(
        f"unknown A2A_ECONOMY_TRANSPORT={choice!r} (expected 'http-local' or 'hermes-a2a')"
    )
