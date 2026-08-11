"""Stage-5 acceptance policy (可否) — pure, deterministic, shared.

Used by the Worker to decide, and by the Evaluator to RE-DERIVE that decision
independently (docs/evaluation-criteria.md §Stage 5 / §Stage 7-B). Because it is
a pure function, the Evaluator recomputing it over the recorded order is what
makes a non-execution verdict verifiable.

Check order matches the published criteria table exactly. The FIRST matching
reason is returned.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from worker_task.endpoint_verify import classify_degraded

PERMITTED_DECLINE_REASONS = (
    "malformed_order",
    "unsupported_scheme",
    "over_budget",
    "degraded_input",
)


def decide(order: dict[str, Any], budget_cap_micro_usd: int) -> dict[str, str | bool]:
    """Return {"accepted": bool, "reason": str}. reason=="ok" when accepted."""
    if "url" not in order or not isinstance(order.get("expect_status"), int):
        return {"accepted": False, "reason": "malformed_order"}

    scheme = urlparse(str(order["url"])).scheme
    if scheme not in ("http", "https"):
        return {"accepted": False, "reason": "unsupported_scheme"}

    cost = order.get("estimated_cost_micro_usd", 0)
    if isinstance(cost, (int, float)) and cost > budget_cap_micro_usd:
        return {"accepted": False, "reason": "over_budget"}

    body = (order.get("response") or {}).get("json")
    degraded, _reason = classify_degraded(body)
    if degraded:
        return {"accepted": False, "reason": "degraded_input"}

    return {"accepted": True, "reason": "ok"}
