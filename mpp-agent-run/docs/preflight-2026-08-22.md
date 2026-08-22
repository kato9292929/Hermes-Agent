# Environment-B preflight recheck — 2026-08-22 (STILL HALTED; cause confirmed)

User switched to a desktop client and asked to re-run. Preflight rechecked; the
gate item `mpp.dev` is still blocked. Cause now confirmed from the agent proxy's
own status endpoint: it is a **gateway egress-policy denial**, not a transient
error. We stop again with the same treatment (no install/account/probe/payment,
no fixture/mock, no retry/circumvention).

## Raw results (single try each)

```
node v22.22.2 ; npm 10.9.7 ; HTTPS_PROXY=http://127.0.0.1:35905

curl -i https://mpp.dev  ->  curl: (56) CONNECT tunnel failed, response 403
                             HTTP/1.1 403 Forbidden

$HTTPS_PROXY/__agentproxy/status (excerpt):
  "noProxy": "...,registry.npmjs.org,jsr.io,pypi.org,...,192.168.0.0/16,..."   # mpp.dev NOT listed
  "recentRelayFailures": [
    { "ts":"2026-08-22T08:47:52Z", "kind":"connect_rejected",
      "detail":"gateway answered 403 to CONNECT (policy denial or upstream failure)",
      "host":"mpp.dev:443" } ]
```

## Verdict

| Preflight item | Result |
|---|---|
| Node.js 20+ | PASS (v22.22.2) |
| npm registry reachable | PASS |
| `mpp.dev` reachable | **FAIL** — remote-environment egress policy denies CONNECT to mpp.dev:443 (403) |
| Tempo wallet funds check | NOT REACHED |

## Why "desktop" did not change this

This Claude Code session runs in a **managed remote (cloud) execution
environment**, not on the user's local machine. Its outbound network is governed
by that environment's **network policy** (chosen when the environment was
created), not by which client app (desktop/web/CLI) the user connects with.
`mpp.dev` is not on the allowlist, so the gateway denies it regardless of the
client. Switching the client to desktop does not alter the remote session's
egress.

## What would actually unblock it (either one)

1. **Change the remote environment's network policy** to permit `mpp.dev` (and the
   Tempo facilitator / settlement hosts it uses) — configured on the Claude Code
   environment, per code.claude.com/docs/en/claude-code-on-the-web. Then re-run
   preflight here.
2. **Run the mpp-agent skill on a real local machine** (e.g. Hermes Desktop with
   open egress) outside this remote session. This session cannot drive that host;
   the record would be produced there and pasted back into `docs/mpp-agent-run.md`.

Until one holds, M3.0 and later stay not-started; all `docs/UNVERIFIED.md` items
remain unverified for this reason.
