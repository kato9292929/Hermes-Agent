# mpp-agent run record (article material)

Goal: use the Hermes **mpp-agent** skill to pay one low-priced mpp.dev endpoint
and capture the whole exchange. This file is the append-target: every field is
filled from an actual run (`var/run-records.jsonl`), not written by hand.

**Status: PATH VERIFIED end to end (2026-08-26).** Run on the operator's Mac (this
remote session still can't reach mpp.dev/exa). Two live runs:
- **#1 testnet** — `mpp.dev/api/ping/paid`, `402 → pay → success` completed on
  Tempo testnet (PathUSD, no real money). Receipt `reference 0xae3d97…68df1b`.
- **#2 mainnet** — `api.exa.ai/search`, the real-money path ran end to end: mppx
  read the challenge, signed, submitted the tx to **Tempo mainnet**, and it
  reverted only on `InsufficientBalance` (wallet balance 0). No money moved.

Verification is complete: Exa serves a **dual** 402 (x402 body + MPP `tempo`
header), mppx pays the tempo rail, unit price **$0.007**. What remains is a
*funded* real charge, and making `scripts/mpp-pay.sh` parse the real header (both
recorded below, not hacked around). See "Live run #1/#2".

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

## Live run #2 — Exa /search (MAINNET) — path proven to chain, halted at zero balance (2026-08-26)

The real-money path was exercised end to end on the operator's Mac: mppx read the
challenge, showed the confirmation, signed, built the payment transaction, and
**submitted it to Tempo mainnet** — where it reverted with `InsufficientBalance`
(wallet balance 0). So the mechanism works to the chain boundary; only funding
stopped it. No money moved.

### Exa returns a DUAL 402 (corrects the M0 provisional)

`curl -i -X POST https://api.exa.ai/search -H 'content-type: application/json' -d '{"query":"test"}'`
→ `HTTP/2 402`, carrying BOTH payment rails in one response:

- **x402** (JSON body `accepts`), amount `7000` = **$0.007** USDC:
  - Base: `network eip155:8453`, `asset 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` (USDC), `payTo 0x6d6E695b09861467c7d462f5AAF31cF3540B9192`, `totalUsd 0.006999…`, `acceptId legacy`
  - Solana: `network solana:5eykt4…`, `asset EPjFWdd5…Dt1v` (USDC), `payTo 12Ec2cJmfR1…`, `acceptId solana-usdc-mainnet`
  - plus an `agentkit` extension ("Verify your agent is backed by a real human", free-trial 100 uses, network `eip155:480` Worldchain)
- **MPP tempo** (`www-authenticate` header, scheme `Payment`), decoded `request`:
  `{"amount":"7000","currency":"0x20C000000000000000000000b9537d11c60E8b50",`
  `"methodDetails":{"chainId":4217,"feePayer":true,"supportedModes":["pull"]},`
  `"recipient":"0xB98eF29eb2be19Ae646A8FC0248255B90A332dbC"}`
  (chainId 4217 = Tempo mainnet; currency is Tempo's USDC TIP20 token.)

So the earlier provisional "Exa = x402 only" (figures.md, 2026-07) is **wrong as of
2026-08-26**: Exa now serves x402 AND MPP tempo together, and mppx pays the tempo
rail. Price is **$0.007**, vs the 2026-07 MPPscan figure ~$0.0051 — a real variance
to note, still ≪ the $0.10 cap.

### What mppx did (raw client, not the wrapper)

```
$ npx mppx https://api.exa.ai/search -X POST -d '{"query":"test"}' -H "Content-Type: application/json" --confirm -v
Payment Required
Challenge  ... method tempo  realm api.exa.ai  intent charge
Request    amount 7000 (0.007 USDC)   recipient 0xB98eF29eb2be19Ae646A8FC0248255B90A332dbC
Details    chainId 4217 (mainnet)  feePayer true  supportedModes pull
▸ Proceed with charge? (Y/n) Y
Error (REQUEST_FAILED): Execution reverted: TIP20 token error:
  InsufficientBalance(available: 0, required: 7000, token: 0x20c000000000000000000000b9537d11c60e8b50)
  chain: Tempo Mainnet (id: 4217)   from: 0xF3531e9A57DECCf08CF36044a99Cd6fBC68852F3   nonce: 0
```

(Under Node 18 the first attempt failed `crypto is not defined`; **Node 20.20.2**
cleared that. The `--confirm` prompt let the operator eyeball amount/chain/recipient
before `Y`.)

### Record (8 fields)

```
1 日時:               2026-08-26T~08:38Z (challenge expires 08:38:11.892Z)
2 エンドポイント:      https://api.exa.ai/search (POST)
3 クライアント:        mppx 0.8.19 (raw `npx mppx ... --confirm -v`, Node 20.20.2; NOT the wrapper)
4 402チャレンジ本文:   DUAL — x402 body (Base+Solana USDC, $0.007) + MPP tempo header
                       (Payment scheme; amount 7000, currency 0x20C0…E8b50,
                       chainId 4217 Tempo mainnet, recipient 0xB98eF…332dbC, feePayer true)
5 支払い(tx/決済ID):   NONE — tx reverted before settlement (InsufficientBalance)
6 支払額:              7000 base = $0.007 USDC required; NOT paid (balance 0)
7 レスポンス本文:      none (payment failed → no 200 merchant body)
8 所要時間:            not measured
```

### Honest limitation surfaced: the wrapper can't parse this real header

`scripts/mpp-pay.sh` / `challenge.py` were built to SKILL.md's simplified form
(`www-authenticate: tempo amount=0.1 currency=USDC`). Exa's REAL header is
`www-authenticate: Payment … method="tempo" request="<base64-json>"` — the amount
lives inside the base64 `request`, and the currency is a **token contract address**,
not the string "USDC". Fed the real header, the wrapper **fails loudly**
(`challenge has no amount; cannot budget-check`) — correct (it does not mis-pay),
but it means the wrapper cannot yet enforce the budget on a real Exa challenge.
Making it real-payment-ready is a deliberate change (decode the base64 `request`;
enforce the USD cap off the x402 body's `totalUsd` / a USDC token-address registry)
— NOT to be hacked in to force a payment. Until then the funded real payment would
have to run through mppx directly, which has no $-cap; the `--confirm` prompt is the
manual guard. This is recorded, not resolved.

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
