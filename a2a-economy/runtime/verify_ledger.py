"""Independent ledger re-verifier.

Purpose (work order M2): make real the claim in docs/evaluation-criteria.md that
"a third party holding the ledger and the criteria can re-derive every verdict".

INDEPENDENCE: this file deliberately does NOT import runtime/evaluator.py,
runtime/worker_policy.py, or worker_task/endpoint_verify.py. Calling the same code
would not be a re-derivation. The acceptance policy, the degraded classifier, the
field check, and the verdict rules below are re-implemented HERE, straight from
the prose of docs/evaluation-criteria.md. If this file and those modules ever
disagree, that disagreement is itself a finding.

INPUT: var/ledger.jsonl only. No network, no external lookup.

For each recorded cycle it re-derives, from the cycle's raw `order`, `decision`,
and `result`:
  - the acceptance decision (from the order alone), and
  - the verdict (from order + the REPORTED decision + result, matching the
    Evaluator's input contract in criteria §7).
It compares both against what the ledger recorded.

Consistency rule (exit code): a cycle is CONSISTENT iff the re-derived verdict
equals the recorded verdict AND the re-derived acceptance equals the recorded
decision — EXCEPT that a re-derived verdict of NON_EXECUTION_INVALID legitimately
means the Worker deviated from the policy, so an acceptance mismatch is expected
there and does not, by itself, make the cycle inconsistent. (A tampered verdict
still fails, because the re-derived verdict would not match the recorded one.)

Exit non-zero if ANY cycle is inconsistent.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any
from urllib.parse import urlparse

# ---- constants transcribed from docs/evaluation-criteria.md (NOT imported) ----
BUDGET_CAP_MICRO_USD = 1_000_000            # criteria §5 default ($1.00)
PERMITTED_DECLINE_REASONS = {
    "malformed_order", "unsupported_scheme", "over_budget", "degraded_input",
}
_ZERO_TX = re.compile(r"^0x0{64}$", re.IGNORECASE)


# ---- re-implemented degraded classifier (criteria §5 / AA stub-detector) ------
def _is_degraded(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("source") == "sample-data":
        return True
    if payload.get("mock") is True:
        return True
    if payload.get("stub") is True:
        return True
    tx = payload.get("txHash") or payload.get("tx_hash")
    if isinstance(tx, str) and _ZERO_TX.match(tx):
        return True
    return False


# ---- re-implemented acceptance policy (criteria §5) ---------------------------
def _redecide(order: dict[str, Any]) -> dict[str, Any]:
    if "url" not in order or not isinstance(order.get("expect_status"), int):
        return {"accepted": False, "reason": "malformed_order"}
    if urlparse(str(order["url"])).scheme not in ("http", "https"):
        return {"accepted": False, "reason": "unsupported_scheme"}
    cost = order.get("estimated_cost_micro_usd", 0)
    if isinstance(cost, (int, float)) and cost > BUDGET_CAP_MICRO_USD:
        return {"accepted": False, "reason": "over_budget"}
    if _is_degraded((order.get("response") or {}).get("json")):
        return {"accepted": False, "reason": "degraded_input"}
    return {"accepted": True, "reason": "ok"}


# ---- re-implemented verification (criteria §5/§7-A) ---------------------------
def _has_path(obj: Any, dotted: str) -> bool:
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False
    return True


def _reverify(order: dict[str, Any]) -> dict[str, Any]:
    expect_status = order["expect_status"]
    expect_fields = list(order.get("expect_json_fields") or [])
    response = order.get("response") or {}
    status_code = response.get("status_code")
    body = response.get("json")

    anomalies: list[str] = []
    if status_code != expect_status:
        anomalies.append("status")
    missing: list[str] = []
    if expect_fields:
        if not isinstance(body, dict):
            missing = list(expect_fields)
        else:
            missing = [f for f in expect_fields if not _has_path(body, f)]
    anomalies += [f"missing:{f}" for f in missing]
    degraded = _is_degraded(body)
    if degraded:
        anomalies.append("degraded")
    return {
        "status_code": status_code,
        "expect_status": expect_status,
        "missing_fields": missing,
        "degraded": degraded,
        "ok": not anomalies,
    }


# ---- re-implemented verdict rules (criteria §7) -------------------------------
def _reverdict(order: dict[str, Any], reported_decision: dict[str, Any],
               result: dict[str, Any] | None) -> str:
    if not reported_decision.get("accepted"):
        # §7-B non-execution path (uses the REPORTED decision, like the Evaluator)
        redecision = _redecide(order)
        reason = reported_decision.get("reason")
        reproduced = (not redecision["accepted"]) and (redecision["reason"] == reason)
        permitted = reason in PERMITTED_DECLINE_REASONS
        return "NON_EXECUTION_VALID" if (reproduced and permitted) else "NON_EXECUTION_INVALID"
    # §7-A executed path
    if result is None:
        return "FAIL"
    recomputed = _reverify(order)
    checks = (
        # reproduced: recomputed core fields match the reported result
        recomputed["status_code"] == result.get("status_code")
        and recomputed["missing_fields"] == result.get("missing_fields")
        and recomputed["degraded"] == result.get("degraded")
        and recomputed["ok"] == result.get("ok"),
        result.get("status_code") == order.get("expect_status"),
        result.get("missing_fields") == [],
        result.get("degraded") is False,
        result.get("ok") is True,
    )
    return "PASS" if all(checks) else "FAIL"


def verify(path: str) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    all_ok = True
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("type") != "cycle":
                continue
            order = rec["order"]
            reported_decision = rec["decision"]
            result = rec.get("result")
            reported_verdict = rec["verdict"]["verdict"]

            re_decision = _redecide(order)
            re_verdict = _reverdict(order, reported_decision, result)

            verdict_match = re_verdict == reported_verdict
            decision_match = (
                re_decision["accepted"] == reported_decision.get("accepted")
                and re_decision["reason"] == reported_decision.get("reason")
            )
            # A genuine Worker deviation is exactly what NON_EXECUTION_INVALID
            # records, so an acceptance mismatch is expected only there.
            deviation_expected = re_verdict == "NON_EXECUTION_INVALID"

            # For executed cycles, the recorded result must REPRODUCE from the
            # recorded order — this catches an input-only tamper (e.g. editing
            # expect_status) even if the verdict label was left untouched.
            result_reproduced: bool | None = None
            if reported_decision.get("accepted"):
                rc = _reverify(order)
                result_reproduced = (
                    result is not None
                    and rc["status_code"] == result.get("status_code")
                    and rc["missing_fields"] == result.get("missing_fields")
                    and rc["degraded"] == result.get("degraded")
                    and rc["ok"] == result.get("ok")
                )
                consistent = verdict_match and decision_match and bool(result_reproduced)
            else:
                consistent = verdict_match and (decision_match or deviation_expected)

            if not consistent:
                all_ok = False
            rows.append({
                "cycle_id": rec["cycle_id"],
                "reported_verdict": reported_verdict,
                "rederived_verdict": re_verdict,
                "verdict_match": verdict_match,
                "reported_decision": f"{reported_decision.get('accepted')}/{reported_decision.get('reason')}",
                "rederived_decision": f"{re_decision['accepted']}/{re_decision['reason']}",
                "decision_match": decision_match,
                "deviation_expected": deviation_expected,
                "result_reproduced": result_reproduced,
                "consistent": consistent,
            })
    return rows, all_ok


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    path = argv[0] if argv else "var/ledger.jsonl"
    rows, all_ok = verify(path)
    if not rows:
        print(f"no cycle records found in {path}", file=sys.stderr)
        return 2
    print(f"re-verifying {len(rows)} cycle(s) from {path}\n")
    for r in rows:
        mark = "OK " if r["consistent"] else "XX "
        print(f"{mark}{r['cycle_id']}")
        print(f"     verdict:  reported={r['reported_verdict']:<22} rederived={r['rederived_verdict']:<22} match={r['verdict_match']}")
        print(f"     decision: reported={r['reported_decision']:<22} rederived={r['rederived_decision']:<22} match={r['decision_match']}"
              + ("  (deviation expected: NON_EXECUTION_INVALID)" if r["deviation_expected"] and not r["decision_match"] else ""))
        if r["result_reproduced"] is not None:
            print(f"     result reproduced from order: {r['result_reproduced']}")
    consistent = sum(1 for r in rows if r["consistent"])
    print(f"\n{consistent}/{len(rows)} cycles consistent")
    if not all_ok:
        print("INCONSISTENT: at least one cycle does not re-derive from the criteria", file=sys.stderr)
        return 1
    print("ALL CONSISTENT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
