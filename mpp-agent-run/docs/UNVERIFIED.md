# Unverified items — mpp-agent-run

## Environment-B smoke test 2026-08-22 (operator's Mac): ping/paid PASSED

`402 → pay → success` completed against `mpp.dev/api/ping/paid` on Tempo testnet
(verbatim challenge + receipt in `docs/mpp-agent-run.md` "Live run #1"). Resolved:

- **#2 live 402 body — CONFIRMED.** `method tempo`, `realm mpp.sh`, `intent charge`,
  `amount 100000 (0.1 PathUSD)`, `recipient 0xf39Fd6…92266`, `chainId 42431 (testnet)`,
  `feePayer true`.
- **#3 MPP-tempo vs x402 — CONFIRMED.** ping/paid returns an **MPP `tempo`**
  challenge (not x402, not Stripe). The mpp-agent skill handles it directly. Exa's
  x402 remains a separate system to be tested on its own.
- **#5 the paid call — CONFIRMED (testnet).** Payment succeeded end to end; still
  UNVERIFIED for a real-money (mainnet USDC) charge and via the budget wrapper.
- **#6 receipt/tx field — CONFIRMED.** The field is **`reference`** (value
  `0xae3d97…68df1b`), alongside `status` and `timestamp`.
- **#7 currency — CONFIRMED (testnet) / OPEN (mainnet).** Testnet currency is
  **PathUSD** (a test token), amount in base units (100000 = 0.1 PathUSD, 6 dp).
  The wrapper correctly treats PathUSD as unknown-currency and refuses; the
  USD/USDC cap applies to the mainnet run.
- **STILL OPEN: real-money run, run-through-the-wrapper, endpoint 200 body (#8-ish),
  timing, facilitator internals, cross-machine account import.**

## Environment-B live run 2026-08-22 (operator's Mac): partial resolution

The remote session still cannot reach mpp.dev, so the operator ran the live steps
on a local macOS machine and pasted the transcript. Resolved / advanced so far
(full transcript in `docs/mpp-agent-run.md` "Live progress"):

- **CONFIRMED — mppx install + account create.** `npx mppx account create`
  succeeded. (Formerly part of #5.)
- **CONFIRMED — M3.0 key storage location.** Keys are stored in the **OS keychain**
  (macOS Keychain), not a dotfile or env var. Address
  `0xF3531e9A57DECCf08CF36044a99Cd6fBC68852F3`. Source: `mppx account create`
  output. (Cross-machine import command still UNVERIFIED — needs `mppx account --help`.)
- **CONFIRMED — the challenge is chain-based (Tempo), not Stripe.** `ping/paid`
  errored `CHAIN_MISMATCH: Challenge requires chainId 42431, but RPC is chainId
  4217` — an on-chain Tempo challenge (42431 = "moderato" testnet). This bears on
  #3 (it is not `method="stripe"`), though the raw `www-authenticate`/`accepts`
  body is still uncaptured (#2 open).
- **STILL UNVERIFIED — the paid call itself (#5 payment).** No payment happened;
  mppx refused on the chain mismatch before charging. Needs testnet funds + the
  matching `--network`/`--rpc-url`, then the call via `scripts/mpp-pay.sh`.
- **STILL UNVERIFIED — #2 live 402 body** (need `curl -i https://mpp.dev/api/ping/paid`),
  **#6 receipt/tx field**, **#7 currency on testnet**, **#8 facilitator response**.

New finding to reconcile later: the smoke-test path is **testnet** (chainId 42431),
whereas the Exa target was scoped as mainnet USDC (~$0.005). The budget cap is
about real money; a testnet smoke test spends no real funds. Decide with the
operator whether the "real payment" record should be a mainnet target after the
testnet path is proven.

## Environment-B attempt 2026-08-17: HALTED AT PREFLIGHT

`mpp.dev` is blocked by the egress proxy (`403 Forbidden`; see
`docs/preflight-2026-08-17.md`). Node 20+ and npm registry passed. Per the work
order we stopped at preflight — no install, account, probe, or payment. Therefore
**all 8 items below remain UNVERIFIED (not resolved to confirmed)**, each for the
same concrete reason: mpp.dev could not be reached from this environment. No item
is deleted; none is marked confirmed. Item #1's status is now "attempted, blocked
at egress" rather than merely "not attempted".



Environment A (done here): skill + provisional-catalog extraction, client
selection, the budget-enforcing wrapper, and its record format — all exercised
against mock 402 fixtures, no network, no payment. Environment B (not gated;
needs keys + network): the live 402 capture, the real payment, the response.

| # | Item | Why unverified | How to verify (env B) | Where it lives |
|---|---|---|---|---|
| 1 | mpp.dev catalog contents & prices | mpp.dev egress-blocked in env A; `mppx` not installed | `mppx` catalog / `stripe directory search "<kw>" --mpp-supported`; replace `docs/mpp-agent-facts.md` §2 provisional figures with live ones | `docs/mpp-agent-facts.md` §2 |
| 2 | Live `www-authenticate` challenge wire format | never captured live | `curl -i https://api.exa.ai/search`; paste full headers | `docs/mpp-agent-run.md` field 4 |
| 3 | Exa: MPP `www-authenticate: tempo …` vs x402 `PAYMENT-REQUIRED` | the skill (SKILL.md:74) and Exa docs (`figures.md:59`) describe different envelopes | inspect the live 402; if x402-only, the wrapper FAILS LOUDLY (by design) and Exa is out of mpp-agent's scope → pick a Tempo-native catalog endpoint instead | `scripts/mpp-pay.sh` (probe), `docs/mpp-agent-facts.md` §3 |
| 4 | Multiple-method challenge ordering | not seen live | capture a `tempo, stripe` header and confirm `choose_client` picks correctly | `scripts/challenge.py` `choose_client` |
| 5 | `mppx` install / account / payment / `-v` receipt | mppx not installed; no funds | `npm i -g mppx`; `mppx account create`; fund; run wrapper | `scripts/mpp-pay.sh` pay branch |
| 6 | Receipt / tx-id field name in `mppx -v` output | output format unknown | run once, then parse the real field (we store full output verbatim rather than guess) | `scripts/mpp-pay.sh` (`SEE_MPPX_OUTPUT` placeholder) |
| 7 | Currency other than USD/USDC/USDC.e | cap is USD; no FX rate | if a live challenge quotes another currency the wrapper REFUSES rather than guessing FX — decide policy with a human | `scripts/challenge.py` `check_budget` |
| 8 | Facilitator / settlement response | env B | observe during a live pay | `docs/mpp-agent-run.md` field 5,7 |

## Verified in environment A (this change)

- Skill facts extracted with `file:line` (`docs/mpp-agent-facts.md` §1), incl. the
  skill's own "three vs five clients" inconsistency (`SKILL.md:18` vs `:30-34`).
- `scripts/challenge.py`: parse + client-choice + budget caps — 13/13 tests pass
  (`scripts/test_challenge.py`), including `method="stripe"`→link-cli,
  zero-amount allowed, per-request and total caps, and fail-loud on unknown
  currency / missing amount / garbage header.
- `scripts/mpp-pay.sh` dry-run across allow / per-request-deny / zero-amount /
  total-cap-deny / stripe→stop / missing-header-FATAL. Spend accrues only on a
  real `paid` record.
