# Unverified items — a2a-economy

Everything below is implemented against the real sources (A2A plugin at Hermes
`v2026.8.3`; AA repo `kato9292929/x402-Autonomous-Agent-`) but could NOT be
exercised end-to-end in environment A (no model key, no wallet, no chain, no
running Hermes runtime). Environment A = the 3-process loop over localhost HTTP
with mock payment, which DOES run here (`scripts/run-cycle.sh`).

Both env-B swaps are each isolated to **one file**:

- **Transport swap point:** `runtime/transport.py` (`get_transport()`, env var
  `A2A_ECONOMY_TRANSPORT`). `http-local` (env A) ↔ `hermes-a2a` (env B).
- **Payment swap point:** `runtime/payment.py` (`get_payment()`, env var
  `A2A_ECONOMY_PAYMENT`). `mock` (env A) ↔ `x402` (env B).

| # | Item | Why unverified | How to verify (env B) | Where to fix |
|---|---|---|---|---|
| 1 | Real A2A transport between 3 Hermes agents | `HermesA2ATransport` needs 3 running Hermes runtimes (models); not runnable in env A | Bring up the 3 agents (below), set `A2A_ECONOMY_TRANSPORT=hermes-a2a`, drive one cycle | `runtime/transport.py` (only) |
| 2 | Real x402 payment | `X402Payment.pay` raises; needs wallet/chain | Set `A2A_ECONOMY_PAYMENT=x402`, bridge to AA `fetchWithPayment` (AA `src/x402.ts:80`) | `runtime/payment.py` (only) |
| 3 | ERC-8004 identity + wallet per actor | placeholders (`*_PLACEHOLDER`); on-chain registration not done | Register each actor via AA `src/erc8004/executor.ts` (`registerAgent`/`setAgentURI`); put real ids in the export | `runtime/export_cycle.py` (`_actor_ids`) |
| 4 | 3 actors as real Hermes agents | `agents/*/config.yaml` not loaded by a Hermes runtime (no model) | `hermes` with each `HERMES_HOME`; confirm `gateway.platforms.a2a` up on its port | `agents/*/config.yaml` |
| 5 | A2A auth/trust (`A2A_PEER_TOKENS`, trusted_peers) | real plugin auth path not exercised | set `A2A_PEER_TOKENS="orchestrator:..,worker:..,evaluator:.."`, confirm identity=name and 401/403 behavior | `agents/*/config.yaml` |
| 6 | Model wiring (`${env:HERMES_MODEL}`) | no API key in env A | set model env + provider key; `hermes -z "hi"` | `agents/*/config.yaml` |
| 7 | Chain / wallet / netting choice for payments | deferred to implementer per work order M5 | decide Base(EVM exact) vs Solana(`registerExactSvmScheme`, AA `src/x402.ts:71`); wire in the payment swap | `runtime/payment.py` + README |
| 8 | A2A partial decline logging | the plugin does NOT audit anti-loop/empty/401/403/429 declines (docs/a2a-facts.md §4) | n/a — mitigated: OUR ledger records every decision, so non-execution is never lost | `runtime/ledger.py` (already mitigated) |

## Environment B — bring-up sketch (M5)

Each actor is its own Hermes instance: distinct `HERMES_HOME` + distinct
`A2A_PORT` (docs/a2a-facts.md §5).

```bash
# per actor (orchestrator 9901 / worker 9902 / evaluator 9903):
HERMES_HOME=~/.hermes-economy/orchestrator \
  cp agents/orchestrator/config.yaml "$HERMES_HOME/config.yaml"   # (+ worker, evaluator)
export A2A_PEER_TOKENS="orchestrator:$T_ORCH,worker:$T_WORK,evaluator:$T_EVAL"
export A2A_TOKEN_WORKER=$T_WORK A2A_TOKEN_EVALUATOR=$T_EVAL
export HERMES_MODEL=... HERMES_MODEL_PROVIDER=... <PROVIDER>_API_KEY=...
# start each: HERMES_HOME=... hermes gateway run   (enables gateway.platforms.a2a)
# then flip the swaps and drive a cycle:
export A2A_ECONOMY_TRANSPORT=hermes-a2a A2A_ECONOMY_PAYMENT=x402
```

Then the Orchestrator drives the loop with the `a2a_call` tool (toolset `a2a`,
enabled only on the orchestrator).
