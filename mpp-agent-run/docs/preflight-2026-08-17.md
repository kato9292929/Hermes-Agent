# Environment-B preflight — 2026-08-17 (HALTED)

Per the env-B work order, preflight is run first; if any item fails we stop
without starting, with no fixture/mock substitution and no retry/circumvention of
a 403 or block. **One item failed → we stopped at preflight.**

## Raw results (single try each)

```
===== PREFLIGHT 2026-08-17T11:44:30Z =====
--- Node version (need 20+) ---
v22.22.2
--- npm version ---
10.9.7
--- proxy env ---
HTTPS_PROXY=http://127.0.0.1:40931
--- npm registry reachability (registry.npmjs.org), single try, 20s ---
HTTP/2 200
date: Mon, 17 Aug 2026 11:44:31 GMT
content-type: application/json
content-length: 2
cache-control: public, immutable, max-age=31557600
--- mpp.dev reachability (single try, 20s, reachability only) ---
curl: (56) CONNECT tunnel failed, response 403
HTTP/1.1 403 Forbidden
Content-Type: text/plain; charset=utf-8
X-Content-Type-Options: nosniff
Content-Length: 65
```

## Verdict

| Preflight item | Result |
|---|---|
| Node.js 20+ | **PASS** — v22.22.2 |
| npm registry reachable | **PASS** — HTTP/2 200 from registry.npmjs.org |
| `mpp.dev` reachable | **FAIL** — the egress proxy returns `403 Forbidden` on CONNECT to mpp.dev (`curl: (56) CONNECT tunnel failed, response 403`) |
| Tempo wallet funds check | **NOT REACHED** — cannot create/inspect an mppx account without reaching mpp.dev / its facilitator |

**PREFLIGHT FAILED: `mpp.dev` is not reachable from this environment.** The block
is an egress-policy 403 at the agent proxy, not a transient error. Per the work
order we do not retry, do not route around it, and do not substitute fixtures. No
install, no account creation, no probe, no payment was attempted.

## What environment B needs before this can proceed

- `mpp.dev` (and the Tempo facilitator / settlement hosts it uses) added to the
  environment's egress allowlist, OR a host that already permits that egress.
- A funded Tempo/mppx account (amount unknown until a live 402 is seen; the
  smallest Exa `/search` charge is provisionally ~$0.005 per `docs/mpp-agent-facts.md`).

## Consequence for the run

The live steps M3.1–M3.4 are **not consumed**. The stopping point is **preflight
(mpp.dev egress blocked)** — this halt is itself the recorded result. Nothing in
`docs/UNVERIFIED.md` was resolved to "confirmed"; every item there remains
unverified for the reason recorded above. The environment-A artifacts
(`scripts/challenge.py`, `scripts/mpp-pay.sh`, the docs) are unchanged.
