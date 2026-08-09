# A to A (Agent-to-Agent) v1.0 — extracted facts

Source: the A2A plugin bundled in Hermes Agent v0.20.0, cloned at tag
`v2026.8.3`. Plugin path: `plugins/platforms/a2a/`
(`plugin.yaml`, `__init__.py`, `adapter.py`, `protocol.py`, `security.py`,
`tools.py`, `DESIGN.md`, `README.md`); user doc
`website/docs/user-guide/messaging/a2a.md`; tests `tests/plugins/test_a2a_plugin.py`.

Every row cites `file:line` in that checkout. Items that could not be confirmed
from source are marked `UNVERIFIED`. Nothing here is guessed; concrete values
were read from the implementation, not transcribed from another repo.

---

## 1. Activation / loading

| Fact | Value | Source |
|---|---|---|
| Plugin kind | bundled **platform** plugin `name: a2a-platform`, `kind: platform` | `plugins/platforms/a2a/plugin.yaml:1-3` |
| Discovery | sweep of `plugins/platforms/` one level deep; needs `plugin.yaml` + `__init__.py:register(ctx)` | `hermes_cli/plugins.py:1362-1366`, `:19-20`; `plugins/platforms/a2a/__init__.py:97` |
| Auto-load | bundled platform → deferred/lazy load, NOT gated by `plugins.enabled` | `hermes_cli/plugins.py:1465-1467`, `:303-307` |
| **Enable inbound platform** | `gateway.platforms.a2a.enabled: true` + `gateway.platforms.a2a.extra.port` | `website/docs/user-guide/messaging/a2a.md:23-30`; `plugins/platforms/a2a/__init__.py:39-44` |
| Connected check | `bool(extra.get("enabled")) or bool(os.getenv("A2A_PORT"))` | `plugins/platforms/a2a/__init__.py:43-44` |
| Port resolution | `int(os.getenv("A2A_PORT") or extra.get("port", 9900))`; default `9900` | `plugins/platforms/a2a/adapter.py:62`, `:346` |
| **Enable outbound tools** | toolset `a2a` (OFF by default) → enable via `hermes tools` | `plugins/platforms/a2a/tools.py:586-595`; `hermes_cli/tools_config.py:156`; `a2a.md:32` |

## 2. Inter-agent call format

| Fact | Value | Source |
|---|---|---|
| Transport | HTTP + **JSON-RPC 2.0**; SSE for streaming; optional push webhooks. stdlib only (`http.server`/`urllib`), no `a2a-sdk` | `protocol.py:5`, `adapter.py:5-16`, `plugin.yaml:27` |
| Protocol version | `PROTOCOL_VERSION = "1.0"`; header `A2A-Version: 1.0` (server rejects mismatch) | `protocol.py:35`; `tools.py:89`; `adapter.py:278-281` |
| Endpoints | `GET /.well-known/agent-card.json` (+ legacy `/agent.json`), `POST /` (JSON-RPC), `GET /`\|`/health`, `GET /metrics` | `adapter.py:219-243` |
| Methods (canonical / legacy) | `SendMessage`/`message/send`, `SendStreamingMessage`/`message/stream`, `GetTask`/`tasks/get`, `ListTasks`, `CancelTask`, `SubscribeToTask`, push-notification-config CRUD | `adapter.py:137-160` |
| Request envelope (outbound) | `{"jsonrpc":"2.0","id":"task-"+uuid16,"method":"SendMessage","params":{"message":{...}}}`; optional `params.tenant` | `tools.py:169-180`; `protocol.py:226-227` |
| Message schema | `{"role":ROLE_USER\|ROLE_AGENT,"parts":[...],"messageId":<hex>,"contextId"?:<str>}` | `protocol.py:261-282` |
| Part types (member-presence, no `kind`) | text `{"text":...,"mediaType":"text/plain"}`, file, data | `protocol.py:234-258` |
| Response (Task) | `{"id":"task-...","contextId":"ctx-...","status":{"state":...,"timestamp":...,"message"?:...},"artifacts"?:[...]}`; SendMessage result is a `{"task"}\|{"message"}` oneof | `protocol.py:367-396`, `:194-213`; `adapter.py:954,962` |
| Task states | SUBMITTED / WORKING / INPUT_REQUIRED / AUTH_REQUIRED / COMPLETED / FAILED / CANCELED / **REJECTED** (terminal: last 4) | `protocol.py:38-47` |
| Sync vs async | Caller sees **synchronous** request/response; adapter blocks on a per-task Future (`_await_reply`). SSE + push are the async options | `adapter.py:928-963`, `:22-24`; `tools.py:186` |

## 3. Peer identity & auth

| Fact | Value | Source |
|---|---|---|
| Outbound addressing | peer **name** from `config.yaml` `a2a_agents.<name>` → `{url, auth, timeout, capabilities, tenant}`, or a direct `http(s)://` URL | `tools.py:53-68` |
| Outbound auth | bearer: `Authorization: Bearer <auth.token>` when `auth.type=="bearer"` | `tools.py:71-74` |
| Inbound auth | bearer token in `Authorization`. `A2A_PEER_TOKENS="alice:tok1,bob:tok2"` → identity = peer **name**; shared `A2A_BEARER_TOKEN` → identity `ip:<addr>`; none → localhost-only, identity `ip:<addr>` | `security.py:49-100` |
| No token/no match | `401` (constant-time `hmac.compare_digest`) | `adapter.py:249-252`; `security.py:96,98` |
| Identity source | derived from presented credential or socket, **never from the request body** | `security.py:11-13`; `adapter.py:247-249` |
| Trust allow-list | `A2A_TRUSTED_PEERS` env or `a2a.trusted_peers` config → else `403 ERR_UNTRUSTED_PEER` (open in localhost-only or with `A2A_ALLOW_ALL_USERS`) | `security.py:133-170`; `adapter.py:295-298` |
| Bind safety | no token ⇒ 127.0.0.1 only; `A2A_HOST` widens only if a token is set | `security.py:103-126`; `adapter.py:347` |
| mTLS | none. HMAC-SHA256 only for outbound push webhook signing (`X-A2A-Signature`) | `security.py:268-279`; `adapter.py:1205` |

## 4. Call logging (incl. rejections)

| Fact | Value | Source |
|---|---|---|
| Audit log | append-only JSONL `$HERMES_HOME/a2a_audit.jsonl`, record `{ts, direction, peer, task_id, summary[:500]}` | `security.py:348-372`; written `adapter.py:733`, `:915`; `tools.py:182` |
| Conversation log | per-context JSONL `$HERMES_HOME/a2a_conversations/<context>.jsonl`, `{ts, role, text, task_id}`; outside compaction | `protocol.py:791-813`; `plugin.yaml:22-25` |
| Task store | in-memory `TaskStore` (cap 500), queryable via GetTask/ListTasks; not persisted | `protocol.py:577-785` |
| **Rejected calls** | application declines (anti-loop, empty task) create a task then `complete(..., STATE_REJECTED)` → queryable, but the early-return paths run BEFORE the audit write, so they are **not** in `a2a_audit.jsonl` | `adapter.py:709-730`, `:733` |
| Transport/authz denials | 401/403 return before task creation → **no task, no audit**; 429 bumps `metrics.rate_limit_triggers` only | `adapter.py:249-252`, `:290-298` |
| Orphaned tasks | no reply within 300s → watchdog marks `STATE_FAILED` | `adapter.py:470-478`; `protocol.py:751-763` |

> **Design implication for this project:** A2A's own logging does NOT reliably
> persist every decline (anti-loop/empty rejections and 401/403/429 are absent
> from `a2a_audit.jsonl`). The work order requires non-execution to be recorded,
> so **our cycle records every decision (execute AND reject) in our own
> append-only ledger** rather than relying on A2A's partial audit. See
> `runtime/ledger.py` / `docs/sample-cycle.md`.

## 5. Multi-instance on one host

| Fact | Value | Source |
|---|---|---|
| Primary isolation | **distinct `A2A_PORT` + distinct `HERMES_HOME`** per instance | `adapter.py:346`; `security.py:348-354`; `protocol.py:791-797`; `adapter.py:871-874` |
| Agent name | `A2A_AGENT_NAME` or `hermes-<hostname>` | `adapter.py:77-86` |
| Public URL | `A2A_PUBLIC_URL` / `X-Forwarded-Host` / `Host` | `adapter.py:197-213` |
| Within one process | served-agent slug (URL path) / tenant / profile under `platforms.a2a.extra.agents` | `adapter.py:490-598` |

## 6. Timeout / retry / failure

| Fact | Value | Source |
|---|---|---|
| Inbound reply timeout | `A2A_REPLY_TIMEOUT` default **300s** → `(STATE_FAILED,"[agent did not reply in time]")` | `adapter.py:69-74`, `:936-942` |
| Outbound call timeout | per-peer `timeout`, default **120s**; card pre-fetch `min(timeout,30)` | `tools.py:37,56-68,157,162` |
| Orphan watchdog | `_ORPHAN_TIMEOUT=300s`, interval `60s` | `adapter.py:63-64,470-475` |
| Push webhook timeout | hard-coded **10s** | `adapter.py:1210` |
| Max body | 1 MB → HTTP 413 | `adapter.py:65,256-257` |
| **Retry** | **none** — no automatic retry of inbound or outbound calls; outbound errors returned to model as strings | `tools.py:281-290`, `:434-449` |
| Failure handling | recorded as terminal task state + returned (does not raise into transport); `tasks_failed` metric | `adapter.py:749-787`, `:922`, `:1251-1266` |
| Anti-loop | `A2A_MAX_PINGPONG_TURNS` default **5** (max 20) per context → `STATE_REJECTED` | `protocol.py:74-83`; `adapter.py:709-722` |
| Rate limit | `A2A_RATE_LIMIT` default **60/min** per identity → 429 | `protocol.py:491-519`; `adapter.py:290-293` |

## 7. Agent card / discovery

- `GET /.well-known/agent-card.json` (canonical v1.0) + legacy `/agent.json`
  (`adapter.py:219-221`). Outbound fetches canonical first, falls back on 404
  (`tools.py:95-111`).
- Card fields: `name`, `description`, `url`, `version`, `provider`,
  `supportedInterfaces[{url,protocolBinding:"JSONRPC",protocolVersion:"1.0",tenant?}]`,
  `capabilities{streaming,pushNotifications,...}`, `defaultInputModes`/
  `defaultOutputModes` `["text/plain"]`, `skills`; adds `securitySchemes.bearer`
  when auth required (`protocol.py:95-144`).
- Skills derived from the live tool registry, restrictable via
  `A2A_ADVERTISED_TOOLSETS` / `advertised_toolsets` (`adapter.py:618-641`;
  `protocol.py:147-179`).
- Peer registry (outbound) is static config `a2a_agents`; no dynamic network
  registry (`tools.py:11-19,53-68`).

## 8. Tools exposed (toolset `a2a`, off by default)

| Tool | Purpose | Source |
|---|---|---|
| `a2a_discover(url)` | fetch + summarize a peer's Agent Card | `tools.py:224-256`, schema `:486-503` |
| `a2a_call(agent, message, context_id?)` | send a task to one peer, return its reply; `context_id` continues a multi-turn exchange | `tools.py:259-302`, `:504-524` |
| `a2a_list()` | list configured peers, persisted conversations, metrics snapshot | `tools.py:305-336`, `:525-532` |
| `a2a_history(context_id, limit?)` | recall a persisted conversation transcript | `tools.py:339-363`, `:533-551` |
| `a2a_orchestrate(capability, message, mode?, context_id?)` | fan-out to peers advertising a capability; modes `all`/`first`/`best` | `tools.py:396-476`, `:552-573` |

Inbound tasks are injected into the live gateway session as a `MessageEvent`
framed as untrusted peer input; the agent's normal reply is the task result
(`adapter.py:762-797`; `security.py:214-222`; `__init__.py:125-135`).

---

## How environment B uses A2A (the real transport)

Each of the 3 actors runs as its own Hermes instance with a distinct
`HERMES_HOME` and `A2A_PORT`. Wiring (all keys above verified):

1. Each actor's `config.yaml`: `gateway.platforms.a2a.enabled: true`,
   `gateway.platforms.a2a.extra.port: <unique>`; enable the `a2a` toolset ONLY
   on actors that must call out (Orchestrator; Evaluator/Worker as needed).
2. Peers listed under `a2a_agents.<name> = {url, auth:{type:bearer,token:${env:...}}, capabilities:[...]}`.
3. Inbound auth via `A2A_PEER_TOKENS="orchestrator:<tok>,worker:<tok>,evaluator:<tok>"`
   so each caller's identity is its name (not `ip:`).
4. The Orchestrator drives the loop with the `a2a_call` tool; the Worker and
   Evaluator reply as normal agent turns.

In this repo, the **single swap point** `runtime/transport.py` selects between
`HttpLocalTransport` (environment A, runs now — same JSON-RPC `SendMessage`
envelope over localhost HTTP) and `HermesA2ATransport` (environment B — the real
plugin, wired as above). See `docs/UNVERIFIED.md`.
