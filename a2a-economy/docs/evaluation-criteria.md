# Evaluation criteria (pre-declared)

**This document is written before the cycle/evaluator implementation and is the
contract the Evaluator applies. It is not amended after the fact to make a run
pass.** It is version-controlled; the timestamp of the commit that introduced it
is the pre-commitment record. The cycle ledger references this file by path so
any result can be checked against the criteria that were in force.

## Why criteria, not "independence," is the guarantee

This is an internal economy (agents owned by one operator). In a closed domain,
an Evaluator running in a separate process is only *formally* independent — it is
still our code, and candidates degenerate. So we do not claim independence as the
safeguard. The safeguards are:

1. **Criteria published in advance** (this file), so the bar cannot be moved to
   fit a result.
2. **A verifiable judgment log** (the append-only ledger), so every verdict can
   be re-derived from the recorded inputs by a third party.

The Evaluator's verdict is therefore a **deterministic re-derivation** from the
published rules over the recorded inputs — never a subjective score. Anyone can
replay it.

## The 8-stage cycle

| # | Stage | Owner | Output recorded |
|---|---|---|---|
| 1 | 目的 (goal) | Orchestrator | the goal text |
| 2 | 分解 (decompose) | Orchestrator | list of work units |
| 3 | 候補 (candidates) | Orchestrator | candidate work orders |
| 4 | 選択 (select) | Orchestrator | the chosen work order |
| 5 | 可否 (accept/decline) | **Worker** | `accepted: bool` + reason |
| 6 | 決済 (payment) | Orchestrator (mock) | payment ref or `null` (skipped if declined) |
| 7 | 評価 (evaluate) | **Evaluator** | verdict + re-derivation |
| 8 | 実績 (record) | Orchestrator | final cycle record (`executed: true\|false`) |

Both paths run to stage 8. A decline at stage 5 skips stage 6 (no payment) but
**still reaches stages 7 and 8** and is recorded as `executed: false` (非執行).
A cycle that leaves no record when it does not execute is a failure of this
system, by design of the work order.

## Stage 5 — Worker acceptance policy (可否), deterministic

Given a work order `{name, url, expect_status, expect_json_fields, response,
estimated_cost_micro_usd}`, the Worker **DECLINES** if ANY of the following holds,
recording the first matching reason; otherwise it **ACCEPTS**.

| Reason code | Condition |
|---|---|
| `malformed_order` | `url` missing, or `expect_status` missing/not an int |
| `unsupported_scheme` | URL scheme not in {`http`, `https`} |
| `over_budget` | `estimated_cost_micro_usd` > `BUDGET_CAP_MICRO_USD` (config, default 1_000_000 = $1.00) |
| `degraded_input` | the `response` payload is a stub/degraded per the classifier below — you cannot honestly verify a fake response |

The stub/degraded classifier (ported from AA `src/stub-detector.ts:9-65`) flags a
payload as degraded when it declares `source == "sample-data"`, `mock == true`,
`stub == true`, or contains an all-zero / obviously fake tx hash
(`0x0000…` or the 32-byte-zero pattern).

`BUDGET_CAP_MICRO_USD` is a config value, not payment volume, and is never used
as a success metric.

## Stage 7 — Evaluator verdict, deterministic

The Evaluator receives the work order, the Worker's stage-5 decision, and (if
accepted) the Worker's result. It **re-derives** the answer from this file's
rules and compares.

**A. Accepted / executed orders.** The Evaluator independently re-runs the
verification (`worker_task/endpoint_verify.py`) on the same input and requires:

| Check | Pass condition |
|---|---|
| reproduced | Evaluator's recomputed result == Worker's reported result (field-by-field) |
| status | `result.status_code == expect_status` |
| fields | `result.missing_fields == []` |
| not degraded | `result.degraded == false` |
| self-consistent | `result.ok == true` |

Verdict = `PASS` iff all five hold, else `FAIL` (with the failing check named).

**B. Declined / non-executed orders.** The Evaluator re-runs the stage-5
acceptance policy on the same order and requires:

| Check | Pass condition |
|---|---|
| reproduced | Evaluator's recomputed decision == `declined` with the SAME reason code |
| permitted | the reason code is one of the four table entries above |

Verdict = `NON_EXECUTION_VALID` iff both hold, else `NON_EXECUTION_INVALID`
(e.g. the Worker declined for an unlisted or non-reproducing reason — that is an
Evaluator failure of the Worker, and is recorded).

## Metrics

Primary metrics (the only ones reported as headline numbers):

- **非執行率 `non_execution_rate`** = declined cycles / total cycles.
- **評価通過率 `eval_pass_rate`** = cycles the Evaluator confirmed valid / total
  cycles, where "valid" = `PASS` (executed) or `NON_EXECUTION_VALID` (declined).

**Explicitly NOT metrics** (label discipline): number of payments, total paid
amount, payment throughput. Self-wallet transfers cannot be distinguished from
self-dealing, so payment volume is never a success indicator. The presence and
validity of decisions — especially non-execution — is what we measure.

## Determinism / reproducibility note

Every input to a verdict (the work order, the worker decision, the result) is
written to the ledger. Because both the acceptance policy and the verifier are
pure deterministic functions, a reviewer with the ledger and this file can replay
every verdict and get the identical answer. No timestamps, randomness, or model
output enters a verdict.
