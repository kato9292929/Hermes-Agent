# a2a-economy — 3-actor internal economy on Hermes A2A v1.0

Three agents — **Orchestrator**, **Worker**, **Evaluator** — run as **separate
processes** and pass one job through an 8-stage cycle. Built on the A to A (A2A)
v1.0 plugin bundled in Hermes Agent `v2026.8.3`. The design (roles) is fixed by
the published spec and is not changed here.

> This is an **internal economy**, not external demand. Payments are between our
> own wallets and are indistinguishable from self-dealing, so **payment count and
> total are never success metrics**. The evidence of autonomy is the **可否
> (accept/decline) judgment — especially non-execution**, which is always
> recorded. See `docs/evaluation-criteria.md`.

## Why separate processes

Judge and actor must be separated across a process boundary; in-process function
splits or subagent delegation do not separate them. Each actor is its own OS
process with its own `HERMES_HOME` and its own A2A port — the isolation unit the
A2A plugin itself uses (`docs/a2a-facts.md` §5).

## The 8-stage cycle

`1 目的 → 2 分解 → 3 候補 → 4 選択 → 5 可否 → 6 決済 → 7 評価 → 8 実績`

Owners: 1–4,6,8 = Orchestrator; 5 = Worker; 7 = Evaluator. Both the execute path
and the reject path run to stage 8; a decline is recorded as `executed: false`.

## Worker task

Endpoint verification (see `docs/worker-selection.md` for why this one and why
the others were rejected): deterministic, machine-checkable, short. The degraded
classifier is ported from AA's `detectDegraded` (`src/stub-detector.ts:9-65`).

## Run it (environment A — no keys, no chain)

```bash
cd a2a-economy
bash scripts/run-cycle.sh        # spawns 3 processes, runs execute + reject cycles
python3 -m runtime.export_cycle  # externally-verifiable export + metrics
```

Outputs land under `var/` (git-ignored): `var/ledger.jsonl` (every stage, actor,
timestamp, in/out) and `var/homes/<role>/a2a_audit.jsonl` (mirrors the real A2A
audit line). A worked sample is in `docs/sample-cycle.md`.

## Layout

```
a2a-economy/
├── docs/
│   ├── a2a-facts.md            # A2A v1.0 spec, file:line citations (M0)
│   ├── worker-selection.md     # candidate adopt/reject (M1)
│   ├── evaluation-criteria.md  # PRE-DECLARED criteria (written before impl)
│   ├── sample-cycle.md         # worked sample, dummy values (M4)
│   └── UNVERIFIED.md           # env-B items + the two swap points
├── runtime/
│   ├── transport.py            # ★ SWAP POINT 1: A2A vs local HTTP
│   ├── payment.py              # ★ SWAP POINT 2: mock vs x402
│   ├── actor.py                # one process per role (HTTP JSON-RPC server)
│   ├── worker_policy.py        # stage-5 acceptance policy (pure)
│   ├── evaluator.py            # stage-7 verdict by re-derivation (pure)
│   ├── ledger.py               # append-only ledger + A2A-style audit
│   ├── export_cycle.py         # external record + metrics
│   ├── kickoff.py              # send a goal to the orchestrator
│   └── economy_config.py       # ports / HERMES_HOME / tokens / budget cap
├── worker_task/endpoint_verify.py  # deterministic verifier (port of detectDegraded)
├── agents/{orchestrator,worker,evaluator}/config.yaml  # env-B Hermes configs
├── goals/{goal-accept,goal-reject}.json                # cycle inputs
└── scripts/run-cycle.sh
```

## The two swap points (each isolated to ONE file)

| Swap | File | Env var | env A | env B |
|---|---|---|---|---|
| Transport | `runtime/transport.py` | `A2A_ECONOMY_TRANSPORT` | `http-local` | `hermes-a2a` (real A2A) |
| Payment | `runtime/payment.py` | `A2A_ECONOMY_PAYMENT` | `mock` | `x402` (AA `fetchWithPayment`) |

Nothing else in the code knows the wire format or how a payment is made. See
`docs/UNVERIFIED.md` for the env-B bring-up (identities, wallets, chain choice).

## toolsets per role (least privilege)

- **Orchestrator** `[a2a]` — may call peers; no terminal/exec.
- **Worker** `[safe]` — web/read only; no terminal/exec/delegation.
- **Evaluator** `[]` — **no tools at all**; it only judges from the message and
  re-derives from the published criteria.

Approvals follow the phase-2 posture: `mode: manual`, `cron_mode: deny`, deny
globs, denial breaker. Secrets are `${env:...}` only.
