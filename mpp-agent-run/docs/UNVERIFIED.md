# Unverified items — mpp-agent-run

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
