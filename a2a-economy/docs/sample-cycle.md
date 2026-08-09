# Sample cycle record (external, verifiable format)

> **All values are DUMMY.** URLs are `https://example.internal/...`; ERC-8004 ids
> and wallets are `*_PLACEHOLDER` (unregistered — env B); the payment reference is
> a deterministic MOCK (no funds moved). No real wallet address or transaction
> hash appears here.

This is the output of `runtime/export_cycle.py` over `var/ledger.jsonl` after one
run of `scripts/run-cycle.sh`, which brought up the three actors as separate
processes (orchestrator :9901, worker :9902, evaluator :9903, each with its own
`HERMES_HOME`) and ran two cycles:

- **cycle-accept-001** — execute path: Worker accepts, verification passes,
  Evaluator `PASS`, `executed: true`.
- **cycle-reject-001** — non-execution path: Worker declines `degraded_input`
  (A2A task state `REJECTED`), payment skipped, Evaluator `NON_EXECUTION_VALID`,
  `executed: false`. The declined cycle still traverses all 8 stages and is
  recorded — non-execution is not discarded.

The export includes, per cycle: the 3 actors' ERC-8004 identifiers (placeholders
until registered), the criteria reference, each stage's timestamp + which actor
produced it, the accept/decline decision and reason, whether payment occurred and
its reference, and the verdict.

## Aggregate metrics

Primary metrics only (payment count/total are excluded by design):

```json
{
  "total_cycles": 2,
  "non_execution_rate": 0.5,
  "eval_pass_rate": 1.0,
  "excluded_by_design": "payment count and total amount are NOT metrics (label discipline; self-wallet transfers are indistinguishable from self-dealing)"
}
```

## cycle-accept-001 (executed)

```json
{
  "cycle_id": "cycle-accept-001",
  "criteria_ref": "a2a-economy/docs/evaluation-criteria.md",
  "actors_erc8004": {
    "orchestrator": {"scheme": "ERC-8004", "status": "UNREGISTERED_PLACEHOLDER", "agent_registry": "eip155:8453:0xIDENTITY_REGISTRY_PLACEHOLDER", "agent_id": "PLACEHOLDER-orchestrator", "wallet": "0xWALLET_PLACEHOLDER"},
    "worker": {"scheme": "ERC-8004", "status": "UNREGISTERED_PLACEHOLDER", "agent_registry": "eip155:8453:0xIDENTITY_REGISTRY_PLACEHOLDER", "agent_id": "PLACEHOLDER-worker", "wallet": "0xWALLET_PLACEHOLDER"},
    "evaluator": {"scheme": "ERC-8004", "status": "UNREGISTERED_PLACEHOLDER", "agent_registry": "eip155:8453:0xIDENTITY_REGISTRY_PLACEHOLDER", "agent_id": "PLACEHOLDER-evaluator", "wallet": "0xWALLET_PLACEHOLDER"}
  },
  "stages": [
    {"stage_no": 1, "stage": "目的(goal)", "actor": "orchestrator", "ts": "2026-08-09T12:32:24Z"},
    {"stage_no": 2, "stage": "分解(decompose)", "actor": "orchestrator", "ts": "2026-08-09T12:32:24Z"},
    {"stage_no": 3, "stage": "候補(candidates)", "actor": "orchestrator", "ts": "2026-08-09T12:32:24Z"},
    {"stage_no": 4, "stage": "選択(select)", "actor": "orchestrator", "ts": "2026-08-09T12:32:24Z"},
    {"stage_no": 5, "stage": "可否(accept/decline)", "actor": "worker", "ts": "2026-08-09T12:32:24Z"},
    {"stage_no": 6, "stage": "決済(payment)", "actor": "orchestrator", "ts": "2026-08-09T12:32:24Z"},
    {"stage_no": 7, "stage": "評価(evaluate)", "actor": "evaluator", "ts": "2026-08-09T12:32:24Z"},
    {"stage_no": 8, "stage": "実績(record)", "actor": "orchestrator", "ts": "2026-08-09T12:32:24Z"}
  ],
  "acceptance": {"accepted": true, "reason": "ok"},
  "payment": {"present": true, "scheme": "mock", "reference": "mock-pay-f89ed86be0bf25de"},
  "executed": true,
  "verdict": "PASS"
}
```

## cycle-reject-001 (non-execution)

```json
{
  "cycle_id": "cycle-reject-001",
  "criteria_ref": "a2a-economy/docs/evaluation-criteria.md",
  "actors_erc8004": {
    "orchestrator": {"scheme": "ERC-8004", "status": "UNREGISTERED_PLACEHOLDER", "agent_registry": "eip155:8453:0xIDENTITY_REGISTRY_PLACEHOLDER", "agent_id": "PLACEHOLDER-orchestrator", "wallet": "0xWALLET_PLACEHOLDER"},
    "worker": {"scheme": "ERC-8004", "status": "UNREGISTERED_PLACEHOLDER", "agent_registry": "eip155:8453:0xIDENTITY_REGISTRY_PLACEHOLDER", "agent_id": "PLACEHOLDER-worker", "wallet": "0xWALLET_PLACEHOLDER"},
    "evaluator": {"scheme": "ERC-8004", "status": "UNREGISTERED_PLACEHOLDER", "agent_registry": "eip155:8453:0xIDENTITY_REGISTRY_PLACEHOLDER", "agent_id": "PLACEHOLDER-evaluator", "wallet": "0xWALLET_PLACEHOLDER"}
  },
  "stages": [
    {"stage_no": 1, "stage": "目的(goal)", "actor": "orchestrator", "ts": "2026-08-09T12:32:25Z"},
    {"stage_no": 2, "stage": "分解(decompose)", "actor": "orchestrator", "ts": "2026-08-09T12:32:25Z"},
    {"stage_no": 3, "stage": "候補(candidates)", "actor": "orchestrator", "ts": "2026-08-09T12:32:25Z"},
    {"stage_no": 4, "stage": "選択(select)", "actor": "orchestrator", "ts": "2026-08-09T12:32:25Z"},
    {"stage_no": 5, "stage": "可否(accept/decline)", "actor": "worker", "ts": "2026-08-09T12:32:25Z"},
    {"stage_no": 6, "stage": "決済(payment)", "actor": "orchestrator", "ts": "2026-08-09T12:32:25Z"},
    {"stage_no": 7, "stage": "評価(evaluate)", "actor": "evaluator", "ts": "2026-08-09T12:32:25Z"},
    {"stage_no": 8, "stage": "実績(record)", "actor": "orchestrator", "ts": "2026-08-09T12:32:25Z"}
  ],
  "acceptance": {"accepted": false, "reason": "degraded_input"},
  "payment": {"present": false, "reference": null},
  "executed": false,
  "verdict": "NON_EXECUTION_VALID"
}
```

## How to reproduce

```bash
cd a2a-economy
bash scripts/run-cycle.sh                 # spawns 3 processes, runs both cycles
PYTHONPATH="$(pwd)" python3 -m runtime.export_cycle   # this document's content
```

Because the acceptance policy and the verifier are pure deterministic functions
(no randomness, no timestamps, no model output in a verdict), a reviewer holding
`var/ledger.jsonl` and `docs/evaluation-criteria.md` can replay every verdict and
obtain the identical result. The per-stage timestamps above are the only
wall-clock values and will differ per run.
