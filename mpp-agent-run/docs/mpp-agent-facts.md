# M0 — mpp-agent skill & mpp.dev catalog facts

Two sources, kept separate:
- **Skill**: `optional-skills/payments/mpp-agent/SKILL.md` in the Hermes upstream
  clone at tag `v2026.8.3` (file:line below). Verified.
- **Catalog**: mpp.dev is **egress-blocked in environment A** (the sandbox proxy
  refuses `mpp.dev`), and `mppx` is not installed, so the live catalog could not
  be pulled. Per the work order this becomes an **environment-B extraction item**;
  the provisional premises below come from the operator's own primary-confirmed
  figures (`x402inc-article-recap/references/figures.md`, captured 2026-07) and
  are labelled `UNVERIFIED (live)`.

---

## 1. mpp-agent skill (file:line)

| Fact | Value | Source |
|---|---|---|
| Identity | `name: mpp-agent`, `version: 0.1.0`, author Teknium, MIT, `platforms: [linux, macos]` | `SKILL.md:2-7` |
| Purpose | pay `HTTP 402` APIs via MPP (mpp.dev) | `SKILL.md:3,16` |
| Client count | prose says "**Three** client options" but the table lists **five** — a self-inconsistency in the skill | `SKILL.md:18` vs `:30-34` |
| Clients (table) | `link-cli` (Stripe Link), Tempo Wallet, Privy Agent CLI, AgentCash, `mppx` | `SKILL.md:30-34` |
| Install (mppx) | `npm install -g mppx` then `mppx account create` | `SKILL.md:56-57` |
| Prereq | Node.js 20+ on PATH; a funded wallet (Tempo/Privy/AgentCash) OR an `mppx` account | `SKILL.md:40-41` |
| Probe | `curl -i <url>` to confirm it speaks MPP | `SKILL.md:67` |
| Challenge form | `www-authenticate: tempo amount=0.1 currency=...` | `SKILL.md:74` |
| Pay (mppx) | `mppx <url>`; POST: `mppx <url> --method POST --data '<json>'`; mppx does the 402 dance and prints the merchant response | `SKILL.md:80-89` |
| Receipt | `mppx <url> -v` | `SKILL.md:96` |
| Verify install | `mppx --version && mppx account list` (exit 0 = ok) | `SKILL.md:121-124` |
| **`method="stripe"` branch** | if the challenge advertises `method="stripe"` → pay via Stripe Link (`link-cli`); otherwise `mppx` pays the Tempo method | `SKILL.md:30,36,112` |
| **Multiple methods** | one header may list several (e.g. `tempo, stripe`); Link's `mpp decode` picks Stripe, `mppx` picks Tempo — pick by which wallet is funded | `SKILL.md:113` |
| **Zero-amount** | `$0.00` challenges want only a proof credential; work without a funded wallet — do NOT refuse as broken | `SKILL.md:114` |
| **Key hygiene** | wallet keys never enter agent context; clients store keys under their own config; do not `cat`/`read_file` them | `SKILL.md:115` |
| Error posture | Link rejects a non-stripe challenge; use the matching wallet instead (do not force it) | `SKILL.md:112` |
| Onboarding skills (per client) | tempo.xyz/SKILL.md, agents.privy.io/skill.md, agentcash.dev/skill.md (fetch with `web_extract`) | `SKILL.md:43-47` |
| Server-side MPP is a DIFFERENT skill | adding 402 to your own API → mpp.dev/quickstart/server + `mppx/{nextjs,hono,express,elysia}` | `SKILL.md:116` |

No `references/` or `scripts/` ship with the skill — it is a single `SKILL.md`.

## 2. mpp.dev catalog — provisional (UNVERIFIED live)

`UNVERIFIED (live): mpp.dev egress blocked in env A; mppx not installed.` The
following are from MPPscan (mpp.dev's own scan) and exa.ai docs as recorded in
`references/figures.md` (captured 2026-07-28 / 2026-07):

- MPP overall (MPPscan, `figures.md:26-32`): 1.9M txns, $277K settled, avg
  **$0.146/call**, buyer:seller ≈ 32:1.
- Per-server average unit price (`figures.md:37-43`): Firecrawl **$0.0024**, Exa
  **$0.0051**, Apollo $0.0149, fal.ai $0.0197, StableEnrich $0.0416,
  CoinGecko **$0.0599**.
- Exa x402 spec (exa.ai docs, `figures.md:54-63`): only `/search` and
  `/contents`; USDC on Base or Solana; **API-key-free** (a present `x-api-key`
  or `Bearer` makes the API-key flow win and x402 is bypassed — mutually
  exclusive); flow `402 + PAYMENT-REQUIRED → resend with PAYMENT-SIGNATURE`;
  rate limit: >5 unauth 402-discovery calls / 60s / IP → 429.
- Discovery layer (`figures.md:153-166`): Stripe Directory indexes
  `mpp.dev` per-call APIs (Tempo); browse with
  `stripe directory search "<kw>" --mpp-supported`.

## 3. Candidate endpoints (≤3) and the choice

| # | Endpoint | What it is | Provisional unit price | Notes |
|---|---|---|---|---|
| 1 | **Exa `/search`** | AI/neural web search | ~**$0.0051**/call (MPPscan `figures.md:39`); Exa min tier ~$0.001 | x402 flow documented (`figures.md:54-63`); API-key-free; topical (flagship MPP search, "Exa MPP" article) |
| 2 | Firecrawl | web scraping / crawl | ~$0.0024/call (`figures.md:38`) — lowest | no challenge-format spec in our sources → more UNVERIFIED |
| 3 | CoinGecko | crypto market data | ~$0.0599/call (`figures.md:43`) | under the $0.10 cap but ~12× Exa; topical |

### Selected: **Exa `/search`**, paid with **`mppx`**

- **Why Exa `/search`.** (a) Lowest-ambiguity target: its 402 payment flow is
  documented in a primary source (`figures.md:54-63`), so we guess the least.
  (b) Single-call price ~$0.005 is far under the $0.10 per-request cap. (c) Most
  topical — search is the flagship MPP category and there is a dedicated "Exa
  MPP" article. (d) API-key-free, so no card/API-key setup is needed for the
  x402 path.
- **Why `mppx`.** The challenge is not `method="stripe"` (Exa pays in USDC, not
  Stripe), so Stripe Link (`link-cli`) is out (`SKILL.md:112`); `mppx` picks the
  Tempo method (`SKILL.md:36,113`). `mppx` is the smallest-dependency client and
  the skill's documented "fastest path" for one-off paid calls (`SKILL.md:34,49`).

### Important env-B ambiguity to resolve first

The mpp-agent skill describes an **MPP** challenge (`www-authenticate: tempo …`,
`SKILL.md:74`), while Exa's own docs describe **x402** headers
(`PAYMENT-REQUIRED`/`PAYMENT-SIGNATURE`, `figures.md:59`). Whether the live Exa
endpoint (via mpp.dev) presents an MPP `www-authenticate` challenge or a bare
x402 challenge is `UNVERIFIED (live)`. Our wrapper parses the MPP
`www-authenticate` form; if Exa returns only x402 headers, the wrapper FAILS
LOUDLY ("not an MPP 402") rather than mis-paying — which is the correct,
non-swallowing behavior. Resolving this is env-B step M3.2.
