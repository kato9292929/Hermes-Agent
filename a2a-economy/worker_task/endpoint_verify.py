"""Deterministic endpoint-verification worker task.

Chosen worker unit (see docs/worker-selection.md): verify one endpoint's
response. The degraded/stub classifier is a port of the AA repo's
`detectDegraded` (src/stub-detector.ts:9-65); the status/field checks mirror the
phase-1 endpoint-healthcheck.

This module is PURE and HERMETIC: it takes an already-captured response payload
and returns a verdict. No network call happens here — that keeps environment A
runnable and every verdict reproducible byte-for-byte. In environment B a fetch
adapter populates `response` from a live paid call; that is the ONLY thing that
changes, and it lives behind runtime/payment.py + a fetch shim, not here.

No exceptions are swallowed into a fake success: a malformed work order raises,
and an unreachable/degraded/unexpected response is reported as an anomaly with
`ok == false`.
"""

from __future__ import annotations

import re
from typing import Any

# All-zero / obviously fake tx hash (0x + 64 zeros), matching AA stub-detector.
_ZERO_TX = re.compile(r"^0x0{64}$", re.IGNORECASE)


def classify_degraded(payload: Any) -> tuple[bool, str]:
    """Port of AA `detectDegraded` (src/stub-detector.ts:9-65).

    Returns (degraded, reason). reason is "" when not degraded.
    """
    if not isinstance(payload, dict):
        return False, ""
    if payload.get("source") == "sample-data":
        return True, "source is sample-data"
    if payload.get("mock") is True:
        return True, "payload marked mock=true"
    if payload.get("stub") is True:
        return True, "payload marked stub=true"
    tx = payload.get("txHash") or payload.get("tx_hash")
    if isinstance(tx, str) and _ZERO_TX.match(tx):
        return True, "all-zero (fake) tx hash"
    return False, ""


def _get_nested(obj: Any, dotted: str) -> bool:
    """True iff the dotted path exists in a decoded JSON object."""
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False
    return True


def verify(order: dict[str, Any]) -> dict[str, Any]:
    """Verify one endpoint work order. Deterministic and pure.

    order = {
      name, url, expect_status (int), expect_json_fields (list[str]),
      response: { status_code (int|None), json (obj|None) }
    }

    Raises ValueError on a malformed order (do NOT swallow) — the Worker's
    stage-5 policy is what turns malformedness into a recorded decline; here we
    fail loudly so a policy bug cannot masquerade as a passing verification.
    """
    if "url" not in order:
        raise ValueError("work order missing 'url'")
    if not isinstance(order.get("expect_status"), int):
        raise ValueError("work order missing integer 'expect_status'")
    response = order.get("response")
    if not isinstance(response, dict):
        raise ValueError("work order missing 'response' object")

    expect_status = order["expect_status"]
    expect_fields = list(order.get("expect_json_fields") or [])
    status_code = response.get("status_code")
    body = response.get("json")

    anomalies: list[str] = []

    if status_code != expect_status:
        anomalies.append(f"unexpected status: got {status_code}, expected {expect_status}")

    missing_fields: list[str] = []
    if expect_fields:
        if not isinstance(body, dict):
            anomalies.append("expected a JSON object body to check fields")
            missing_fields = list(expect_fields)
        else:
            for f in expect_fields:
                if not _get_nested(body, f):
                    missing_fields.append(f)
    for f in missing_fields:
        anomalies.append(f"missing required JSON field: {f}")

    degraded, degraded_reason = classify_degraded(body)
    if degraded:
        anomalies.append(f"degraded response: {degraded_reason}")

    return {
        "name": order.get("name") or order["url"],
        "url": order["url"],
        "expect_status": expect_status,
        "status_code": status_code,
        "missing_fields": missing_fields,
        "degraded": degraded,
        "degraded_reason": degraded_reason,
        "anomalies": anomalies,
        "ok": not anomalies,
    }
