# mpp-agent run record (article material)

Goal: use the Hermes **mpp-agent** skill to pay one low-priced mpp.dev endpoint
and capture the whole exchange. This file is the append-target: every field is
filled from an actual run (`var/run-records.jsonl`), not written by hand.

**Status: SMOKE TEST PASSED on the operator's Mac (2026-08-22).** This remote
session still cannot reach `mpp.dev` (egress 403; see `docs/preflight-*.md`), so
the operator ran the live steps locally. The `402 → pay → success` cycle
**completed** against `mpp.dev/api/ping/paid` on **Tempo testnet** (PathUSD test
token — no real money). This confirmed the mpp-agent path and answered UNVERIFIED
#3 (ping/paid returns an **MPP `tempo`** challenge, which the skill handles
directly — Exa's x402 is a separate system). Still pending: the real-money
payment to the Exa mainnet target, via the budget wrapper. See "Live run #1"
below for the verbatim challenge + receipt.

## Live progress — operator's Mac (2026-08-22)

Environment: operator macOS (open egress), NOT this remote session. Commands and
output pasted by the operator. Only the public address and identifiers are
recorded; no key/seed (SKILL.md:115).

### M3.0 — where `mppx account create` stores the account: CONFIRMED

```
$ npx mppx account create
Account "main" saved to keychain.
Address 0xF3531e9A57DECCf08CF36044a99Cd6fBC68852F3
Fund testnet tokens: mppx account fund --account main --network testnet
```

- **Storage: the OS keychain** (macOS Keychain), not a dotfile or an env var.
  Account label `main`; address `0xF3531e9A57DECCf08CF36044a99Cd6fBC68852F3`.
- **Import of a pre-funded account across machines:** since the secret lives in
  the OS keychain, moving it means a keychain-level import, not copying a file.
  The exact `mppx` import command is still `UNVERIFIED` — resolve with
  `npx mppx account --help` (do not print the key).

### M3.2/M3.3 — `ping/paid` smoke test: stopped at CHAIN_MISMATCH (no charge)

```
$ npx mppx https://mpp.dev/api/ping/paid
Error (CHAIN_MISMATCH): Challenge requires chainId 42431, but RPC is chainId 4217.
Use --network testnet or --rpc-url https://rpc.moderato.tempo.xyz.
```

- The `ping/paid` challenge targets **chainId 42431** (Tempo "moderato" testnet,
  per the suggested `rpc.moderato.tempo.xyz`); the freshly-created account's
  default RPC is **chainId 4217**. mppx refused rather than paying on the wrong
  chain — no payment occurred, budget untouched.
- This was raw `npx mppx`, NOT the budget wrapper `scripts/mpp-pay.sh`. Per the
  work order the actual paid call must go through the wrapper (budget + record);
  the raw call here only surfaced the chain requirement.
- Next: capture the raw 402 body (`curl -i https://mpp.dev/api/ping/paid`) so the
  challenge's amount/currency/method/chain are on record, then, if funded on
  testnet, run the paid call through the wrapper with the matching network.

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

## Live run #1 — mpp.dev ping/paid (TESTNET) — SUCCESS (2026-08-22)

The `402 → pay → success` cycle completed on the operator's Mac. This is the
mpp.dev **test** endpoint on Tempo **testnet** (chainId 42431), paid in **PathUSD**
(a test token) — so it proves the mpp-agent payment path end to end, but **no real
money moved**. The real-money target (Exa mainnet USDC) is still pending.

Command (operator's Mac):
```
npx mppx https://mpp.dev/api/ping/paid --network testnet -v
```

Verbatim `-v` output (challenge + receipt):
```
Payment Required
  Challenge  description Ping endpoint access   expires 2026-08-22T09:27:00.096Z
             intent charge   method tempo   realm mpp.sh
  Request    amount 100000 (0.1 PathUSD)
             recipient 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
  Details    chainId 42431 (testnet)   feePayer true

Payment Receipt
  reference 0xae3d979055ddbd66f52752b890c860881974b800b3ddc5c325776a2a3768df1b
  status success   timestamp 2026-08-22T09:22:01.950Z
```

Record (8 fields):
```
1 日時:               2026-08-22T09:22:01.950Z (receipt timestamp)
2 エンドポイント:      https://mpp.dev/api/ping/paid
3 クライアント:        mppx (raw `npx mppx ... --network testnet -v`; NOT via the
                       budget wrapper — see note below)
4 402チャレンジ本文:   method tempo / realm mpp.sh / intent charge /
                       amount 100000 (0.1 PathUSD) /
                       recipient 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 /
                       chainId 42431 (testnet) / feePayer true /
                       description "Ping endpoint access" / expires 2026-08-22T09:27:00.096Z
5 支払い(決済ID):     reference 0xae3d979055ddbd66f52752b890c860881974b800b3ddc5c325776a2a3768df1b
6 支払額:              100000 base units = 0.1 PathUSD (TESTNET token, not USD)
7 レスポンス本文:      receipt status "success" (the ping endpoint's 200 body was
                       not separately shown by `mppx -v`; capture it next run)
8 所要時間:            not measured (raw mppx has no timer; the wrapper records duration_ms)
```

Notes / caveats (kept honest):
- **Not through the budget wrapper.** This was raw `mppx`. The wrapper
  (`scripts/mpp-pay.sh`) would have treated currency **PathUSD** as *unknown* and
  **refused** (fail-loud, no invented FX) — which is the correct conservative
  behavior. So the wrapper cannot pay a PathUSD testnet challenge as-is, and we do
  NOT hack PathUSD into the USD cap to force it. The wrapper is for the real-money
  USD/USDC path (Exa mainnet).
- 0.1 PathUSD would map to exactly the $0.10 per-request cap **if** PathUSD were
  treated 1:1 with USD — another reason the wrapper's refuse-unknown-currency rule
  matters on mainnet.
- An earlier attempt showed `crypto is not defined` under an older Node; switching
  to **Node 20.20.2** cleared it (alongside `--network testnet` clearing
  CHAIN_MISMATCH).

## Live run #2 — Exa /search (MAINNET, real USDC) — PENDING

```
0 状態:               PENDING — needs real USDC funding (human decision) + run via
                      scripts/mpp-pay.sh (budget-enforced). Amount must be ≤ $0.10.
1-8:                  UNVERIFIED (live)
```

If a run is interrupted, record WHERE it stopped (challenge-method mismatch /
insufficient funds / client prerequisite unmet / facilitator response) verbatim —
per the work order a broken run is also article material.

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
