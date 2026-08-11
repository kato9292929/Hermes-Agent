# Worker candidate selection

Goal: pick ONE worker task for the 3-actor loop. Two hard conditions (work order
M1): the result's pass/fail must be **machine-checkable**, and each item must be
**short** to execute. I read the AA repo
(`kato9292929/x402-Autonomous-Agent-`) to see which candidate units actually
exist and which meet both conditions.

> Framing that shaped the decision: **AA is a client** — it *pays to read*
> external x402 products (catalyst, JIN, analyst data); it does not *host*
> catalyst/MAP/JIN/X-alpha services. So "pick a worker unit" means "pick a unit
> of work AA already performs locally," not "call an external product."

## Candidates

| Candidate | Exists in AA? | Where | Input → Output | Machine-checkable? | Short? | Verdict |
|---|---|---|---|---|---|---|
| endpoint 1件の検証 (MAP) | **Yes** (verification logic; no literal "MAP" name) | `src/stub-detector.ts:36-65` (`detectDegraded`), `src/scripts/verify-products.ts:43-125` (`probe`/`ProbeResult`), `src/caller.ts:10-91` | endpoint response JSON → `{degraded:bool, reason}` / status enum | **Yes** — pure, deterministic; `detectDegraded` is hermetic (no network) | Yes | **ADOPT** |
| catalyst 1件の判定 (resolver) | Partial analog only | `src/modes/scoring.ts:72-121` (`scoreDecision`) | 3 signals → `{score, action:BUY\|SKIP, ...}` | Yes (pure, tested) | Yes | Reject — it is a **trade** BUY/SKIP judgment; using it as the unit drags market/execution framing in, which the label discipline forbids |
| 観測1日分 (JIN) | Consumed, not produced | `src/config.ts:131-150` (external URLs), `src/modes/modeB.ts:23-76` (`saveExternalData`) | scheduled fetch → arbitrary daily JSON blob | Partial (parse/presence only; content shape unconfirmed) | No (a day's blob) | Reject — not a short deterministic per-item output AA produces |
| X post 1件の構造化 (X-alpha) | **No** | — (grep negative) | — | — | — | Reject — not implemented in this repo |
| 記事の要約・翻訳 1件 | Present but unfit | `src/lib/note-generator.ts:51-79` (`generateNoteArticle`, Claude, `temperature:0.5`) | ticker JSON → free-form JP article | **No** — non-deterministic LLM prose, no schema | No (long) | Reject — not machine-checkable, not short |

## Decision

**Adopt: endpoint verification ("MAP" candidate).** Reasons:

1. **Machine-checkable, deterministic, hermetic.** The core is a pure function
   over an endpoint's response: expected-status match, required-field presence,
   and a stub/degraded classifier modeled on AA's `detectDegraded`
   (`src/stub-detector.ts:36-65`). Given the same input it always yields the
   same verdict — the Evaluator can re-check it independently.
2. **Short per item.** One endpoint → one small structured verdict.
3. **Already an existing work unit** on both sides: AA verifies the endpoints it
   pays for; our phase-1 `endpoint-healthcheck` skill verifies endpoints too.
   Reusing this keeps the loop grounded in real work, not a toy.
4. **Label-discipline clean.** Endpoint verification carries no market / demand /
   trade semantics, unlike the `scoreDecision` trade judgment.

## What the worker actually does (this repo)

`worker_task/endpoint_verify.py` — a deterministic verifier. Input: one work
order `{name, url, expect_status, expect_json_fields, response}` where `response`
is a captured/mock endpoint payload (env A stays hermetic; env B fetches live).
Output: `{ok:bool, status_code, expect_status, missing_fields:[...],
degraded:bool, degraded_reason, anomalies:[...]}`. The degraded classifier is a
port of AA's `detectDegraded` rules (`src/stub-detector.ts:9-65`): a payload
marked `source:"sample-data"`, `mock:true`, or carrying an all-zero / obviously
fake tx hash is flagged degraded.

## Why this makes non-execution visible (the key autonomy evidence)

The Worker's **可否 (accept/decline)** at stage 5 is where autonomy shows in a
closed economy. The Worker declines a work order — recorded as **非執行** — when
it fails a pre-declared acceptance policy (see `docs/evaluation-criteria.md`):
e.g. the input payload is itself a **stub/degraded** (you cannot honestly verify
a fake response), the URL scheme is unsupported, or the estimated cost exceeds
the budget cap. A declined order still travels all 8 stages and is written to the
ledger as `executed:false` — mirroring AA's own `executed:false` record-only
convention (`src/modes/modeA.ts:12-14,186`).
