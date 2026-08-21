# Environment-B preflight recheck — 2026-08-21 (STILL HALTED)

Re-run attempt per the env-B supplement. The gate item `mpp.dev` is still blocked,
so we stop again with the same treatment as 2026-08-17 — no install, no account,
no probe, no payment, no fixture/mock substitution, no retry/circumvention.

## Raw result (single try)

```
===== PREFLIGHT RECHECK 2026-08-21T06:18:23Z =====
--- mpp.dev reachability (single try, 20s, reachability only) ---
curl: (56) CONNECT tunnel failed, response 403
HTTP/1.1 403 Forbidden
Content-Type: text/plain; charset=utf-8
X-Content-Type-Options: nosniff
Content-Length: 65
Connection: close
```

## Verdict

| Preflight item | Result |
|---|---|
| Node.js 20+ | PASS (v22.22.2, confirmed 2026-08-17; unchanged) |
| npm registry reachable | PASS (confirmed 2026-08-17; unchanged) |
| `mpp.dev` reachable | **FAIL** — egress proxy still returns `403 Forbidden` on CONNECT |
| Tempo wallet funds check | NOT REACHED |

**PREFLIGHT FAILED AGAIN: the egress allowlist for `mpp.dev` has not taken effect
in this environment.** The human-side egress + funding work is still pending here.

## Not started (per the gate)

Because preflight failed, none of the supplement's steps were started:
- **M3.0** (confirm where `mppx account create` stores keys; define how to import a
  pre-funded account from another machine) — NOT done. It is the first live step,
  inside the preflight gate. It only needs npm (which passed), so it *could* be
  done independently of mpp.dev — but the env-B rule is "if any preflight item
  fails, stop without starting," so we hold rather than begin the live run. If the
  operator wants M3.0 confirmed ahead of egress being fixed, that is a separate
  explicit go-ahead.
- **M3.2 addition** (whether mppx's default enables `evm.charge`/x402-exact),
  **ping/paid smoke test** (`https://mpp.dev/api/ping/paid`), **M3.3** live pay —
  all NOT started; all require mpp.dev egress.

## To proceed

Same as 2026-08-17: `mpp.dev` (+ its Tempo facilitator / settlement hosts) must be
on the environment's egress allowlist, and a pre-funded mppx/Tempo account must be
importable here. When both hold, re-run preflight; on pass, start at M3.0 and use
the unchanged `scripts/mpp-pay.sh`. The task-total cap stays $0.50 (the ping/paid
smoke test counts inside it).
