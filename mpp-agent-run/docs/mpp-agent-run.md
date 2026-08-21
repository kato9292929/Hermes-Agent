# mpp-agent run record (article material)

Goal: use the Hermes **mpp-agent** skill to pay one low-priced mpp.dev endpoint
and capture the whole exchange. This file is the append-target: every field is
filled from an actual run (`var/run-records.jsonl`), not written by hand.

**Status: environment-B HALTED AT PREFLIGHT (rechecked 2026-08-21).** Node 20+ and
the npm registry are reachable, but **`mpp.dev` is still blocked by the egress
proxy (`403 Forbidden`)** on both 2026-08-17 and the 2026-08-21 re-run, so no
install, account, probe, or payment was attempted (no fixture/mock substitution,
no retry/circumvention — per the work order). Stopping point is preflight; raw
logs in `docs/preflight-2026-08-17.md` and `docs/preflight-2026-08-21.md`. Every
unfilled field below remains `UNVERIFIED (live)`.

## Target & client (from M0)

| Field | Value |
|---|---|
| Endpoint | **Exa `/search`** (`https://api.exa.ai/search`) — AI web search |
| Why chosen | lowest-ambiguity target (x402 flow documented), ~$0.005/call ≪ $0.10 cap, most topical, API-key-free — see `docs/mpp-agent-facts.md` §3 |
| Client | **`mppx`** (non-stripe challenge → mppx pays Tempo; smallest dep; skill's fastest path) |
| Per-request cap | **$0.10** (enforced in `scripts/challenge.py` / `scripts/mpp-pay.sh`) |
| Task-total cap | **$0.50** (cumulative, tracked in `var/spend-ledger.jsonl`) |

## Assembled call (budget-enforced wrapper)

```bash
# 0. install + account (env B) — SKILL.md:56-57, keys stay in mppx config
npm install -g mppx && mppx account create

# 1. probe + parse + budget-check + pay + record, all through the wrapper:
bash scripts/mpp-pay.sh https://api.exa.ai/search
#    (POST variant: bash scripts/mpp-pay.sh <url> --method POST --data '<json>')
```

The wrapper probes with `curl -i` (SKILL.md:67), parses the `www-authenticate`
challenge, refuses anything over the caps, and only then runs `mppx <url> -v`
(SKILL.md:80,96). It never reads wallet keys (SKILL.md:115) and exits non-zero on
any unexpected response.

## Record fields (filled per run)

| # | Field | Source |
|---|---|---|
| 1 | 日時 (UTC) | `run-records.jsonl.ts` |
| 2 | エンドポイント | `.url` |
| 3 | クライアント | `.client` |
| 4 | 402チャレンジ本文（全文） | `.www_authenticate` (+ raw headers saved by the probe) |
| 5 | 支払い (tx / 決済ID) | `.payment_ref` (env B, from `mppx -v` receipt) |
| 6 | 支払額 | `.amount_usd` |
| 7 | レスポンス本文（全文） | `.response_body` (env B, verbatim mppx output) |
| 8 | 所要時間 | wrapper-measured `duration_ms` (env B) |

## Live run (environment B) — to be filled

```
0 停止点:             PREFLIGHT FAILED 2026-08-17 — mpp.dev egress 403 (docs/preflight-2026-08-17.md)
1 日時:               UNVERIFIED (live)
2 エンドポイント:      https://api.exa.ai/search
3 クライアント:        mppx
4 402チャレンジ本文:   UNVERIFIED (live) — paste the FULL www-authenticate line(s)
                       and raw 402 headers here; if Exa returns x402
                       PAYMENT-REQUIRED instead of MPP www-authenticate, the
                       wrapper FAILS LOUDLY and that failure is the record
5 支払い(tx/決済ID):   UNVERIFIED (live)
6 支払額:              UNVERIFIED (live) — must be ≤ $0.10 or the wrapper stops
7 レスポンス本文:      UNVERIFIED (live) — full merchant JSON
8 所要時間:            UNVERIFIED (live)
```

If the run is interrupted, record WHERE it stopped (challenge-method mismatch /
insufficient funds / client prerequisite unmet / facilitator response) verbatim
— per the work order a broken run is also article material.

## Environment-A demonstration (no network, no payment)

The wrapper's probe→parse→budget→record pipeline is exercised in env A against
mock 402 fixtures (`fixtures/*.http`). This proves the budget enforcement and
recording work; it is NOT a live payment (`dry_run: true`).

```json
{"ts": "2026-08-17T04:05:52Z", "url": "https://api.exa.ai/search", "client": "mppx", "dry_run": true, "www_authenticate": "tempo amount=0.005 currency=USDC", "budget_decision": "dry_run_allow", "amount_usd": 0.005, "payment_ref": null, "http_status": null, "response_body": null}
{"ts": "2026-08-17T04:05:52Z", "url": "https://api.exa.ai/search", "client": "mppx", "dry_run": true, "www_authenticate": "tempo amount=0.25 currency=USDC", "budget_decision": "budget_denied", "amount_usd": 0.25, "payment_ref": null, "http_status": null, "response_body": null}
```

Row 1: a $0.005 challenge is within caps → would pay (dry-run). Row 2: a $0.25
challenge exceeds the $0.10 per-request cap → **budget_denied**, no payment. The
wrapper also stops on the task-total cap ($0.50 cumulative), on a `method="stripe"`
challenge (→ use the stripe-link-cli skill, not mppx), and FAILS LOUDLY when the
response carries no `www-authenticate` header. `dry_run` records never add to
`var/spend-ledger.jsonl`.
