"""Stage-7 Evaluator verdict — pure, deterministic re-derivation.

Applies docs/evaluation-criteria.md over the recorded inputs. The Evaluator does
NOT trust the Worker's word: it re-runs the acceptance policy (declined path) or
re-runs the verification (executed path) and compares. This is the verifiability
guarantee — the same inputs always yield the same verdict.
"""

from __future__ import annotations

from typing import Any

from runtime import worker_policy
from worker_task import endpoint_verify


def evaluate(order: dict[str, Any], decision: dict[str, Any],
             result: dict[str, Any] | None, budget_cap_micro_usd: int) -> dict[str, Any]:
    redecision = worker_policy.decide(order, budget_cap_micro_usd)

    # --- Declined / non-execution path (criteria §7-B) ---
    if not decision.get("accepted"):
        reason = decision.get("reason")
        reproduced = (not redecision["accepted"]) and (redecision["reason"] == reason)
        permitted = reason in worker_policy.PERMITTED_DECLINE_REASONS
        valid = reproduced and permitted
        return {
            "verdict": "NON_EXECUTION_VALID" if valid else "NON_EXECUTION_INVALID",
            "path": "non_execution",
            "reported_reason": reason,
            "recomputed_reason": redecision["reason"],
            "checks": {"reproduced": reproduced, "permitted": permitted},
        }

    # --- Accepted / executed path (criteria §7-A) ---
    if result is None:
        return {
            "verdict": "FAIL",
            "path": "executed",
            "checks": {"result_present": False},
            "failing": ["result_present"],
        }

    recomputed = endpoint_verify.verify(order)
    checks = {
        "reproduced": recomputed == result,
        "status": result.get("status_code") == order.get("expect_status"),
        "fields": result.get("missing_fields") == [],
        "not_degraded": result.get("degraded") is False,
        "self_consistent": result.get("ok") is True,
    }
    failing = [k for k, v in checks.items() if not v]
    return {
        "verdict": "PASS" if not failing else "FAIL",
        "path": "executed",
        "checks": checks,
        "failing": failing,
    }
