# mpp-agent-run

Use the Hermes **mpp-agent** skill (`optional-skills/payments/mpp-agent`, author
Teknium, MIT) to pay one low-priced mpp.dev endpoint and capture the whole
exchange as article material. This is "we actually ran the skill", not a new
payment implementation — the AA repo's `src/x402.ts` is deliberately not used.

The deliverable is the **record**. Environment A here is: extract the skill +
provisional catalog, choose the client, assemble the budget-enforced call, and
fix the record format. Environment B (keys + network) does the live pay — not
gated; unfilled fields are labelled `UNVERIFIED (live)`.

## Target & client

- **Endpoint:** Exa `/search` (~$0.005/call) — why in `docs/mpp-agent-facts.md` §3.
- **Client:** `mppx` (challenge is not `method="stripe"`, so mppx pays the Tempo
  method; smallest dependency; the skill's fastest path).
- **Budget caps (enforced):** per-request **$0.10**, task total **$0.50**.

## Layout

```
mpp-agent-run/
├── docs/
│   ├── mpp-agent-facts.md   # M0: skill facts (file:line) + provisional catalog + candidates + choice
│   ├── mpp-agent-run.md     # M2: the record template (fills from a run)
│   └── UNVERIFIED.md        # env-B items
├── scripts/
│   ├── challenge.py         # pure: parse www-authenticate, choose client, enforce caps
│   ├── mpp-pay.sh           # wrapper: probe → parse → budget → pay(mppx) → record
│   └── test_challenge.py    # env-A tests (13/13)
├── fixtures/*.http          # mock 402 responses for the hermetic dry-run
└── var/                     # append-only run records + spend ledger (git-ignored)
```

## Run

```bash
cd mpp-agent-run

# Environment A — hermetic dry-run (no network, no payment):
python3 scripts/test_challenge.py
bash scripts/mpp-pay.sh https://api.exa.ai/search --challenge-file fixtures/challenge-tempo.http

# Environment B — live (needs Node 20+, mppx, a funded account):
npm install -g mppx && mppx account create      # keys stay in mppx config
bash scripts/mpp-pay.sh https://api.exa.ai/search
```

## Guarantees (per the work order)

- **Budget is enforced in code**: over-cap (per-request or cumulative) → stop +
  record, exit non-zero. Raising the cap is a human decision.
- **No silent failure**: a response without `www-authenticate`, an unknown
  currency, a missing amount, a `mppx` non-zero exit, or a garbage challenge all
  FAIL LOUDLY and are recorded — nothing is swallowed.
- **Zero-amount challenges are honored**, not treated as broken (SKILL.md:114).
- **Wallet keys never enter the agent context** (SKILL.md:115): the wrapper only
  runs `mppx` and never reads key files.
- **Only the selected endpoint is paid**; a `method="stripe"` challenge stops the
  wrapper (use the stripe-link-cli skill) rather than being paid via mppx.

See `docs/UNVERIFIED.md` for exactly what remains for environment B.
