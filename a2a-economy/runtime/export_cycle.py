"""Export the ledger into an externally-verifiable record + aggregate metrics.

Reads var/ledger.jsonl and emits, per cycle: the 3 actors' ERC-8004 standard
identifiers (placeholders until registered — env B), the criteria reference, each
stage's timestamp, the accept/decline decision and reason, whether payment
occurred and its reference, and the verdict. Aggregate metrics are the two
label-safe ones only: non-execution rate and eval pass rate.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from runtime import economy_config as C

# ERC-8004 registration is done in environment B (see docs/UNVERIFIED.md). Until
# then each actor carries a clearly-labelled placeholder, not a fake id.
_ERC8004_PLACEHOLDER = {
    "scheme": "ERC-8004",
    "status": "UNREGISTERED_PLACEHOLDER",
    "agent_registry": "eip155:8453:0xIDENTITY_REGISTRY_PLACEHOLDER",
}


def _actor_ids() -> dict[str, Any]:
    return {
        role: {**_ERC8004_PLACEHOLDER,
               "agent_id": f"PLACEHOLDER-{role}",
               "wallet": "0xWALLET_PLACEHOLDER"}
        for role in C.ROLES
    }


def _load(path: str) -> tuple[list[dict], list[dict]]:
    stages, cycles = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            (cycles if rec.get("type") == "cycle" else stages).append(rec)
    return stages, cycles


def build_export(path: str = C.LEDGER) -> dict[str, Any]:
    stages, cycles = _load(path)
    by_cycle: dict[str, list[dict]] = {}
    for s in stages:
        by_cycle.setdefault(s["cycle_id"], []).append(s)

    exported = []
    for c in cycles:
        cid = c["cycle_id"]
        st = sorted(by_cycle.get(cid, []), key=lambda x: x["stage_no"])
        payment = c.get("payment")
        exported.append({
            "cycle_id": cid,
            "criteria_ref": c["criteria_ref"],
            "actors_erc8004": _actor_ids(),
            "stages": [{"stage_no": x["stage_no"], "stage": x["stage"],
                        "actor": x["actor"], "ts": x["ts"]} for x in st],
            "acceptance": {"accepted": c["decision"]["accepted"],
                           "reason": c["decision"]["reason"]},
            "payment": ({"present": False, "reference": None} if payment is None
                        else {"present": True, "scheme": payment["scheme"],
                              "reference": payment["reference"]}),
            "executed": c["executed"],
            "verdict": c["verdict"]["verdict"],
        })

    total = len(cycles)
    non_exec = sum(1 for c in cycles if not c["executed"])
    valid = sum(1 for c in cycles
                if c["verdict"]["verdict"] in ("PASS", "NON_EXECUTION_VALID"))
    metrics = {
        "total_cycles": total,
        "non_execution_rate": round(non_exec / total, 4) if total else None,
        "eval_pass_rate": round(valid / total, 4) if total else None,
        "excluded_by_design": "payment count and total amount are NOT metrics "
                              "(label discipline; self-wallet transfers are "
                              "indistinguishable from self-dealing)",
    }
    return {"metrics": metrics, "cycles": exported}


def main(argv: list[str] | None = None) -> int:
    path = argv[0] if argv else C.LEDGER
    print(json.dumps(build_export(path), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
