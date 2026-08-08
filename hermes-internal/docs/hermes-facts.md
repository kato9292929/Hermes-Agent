# Hermes Agent — extracted facts (v0.20.0 / tag `v2026.8.3`)

Everything below was read from the actual upstream source, cloned at tag
`v2026.8.3` (HEAD commit message: `chore: release v0.20.0 (2026.8.3)`):

```
git clone --depth 1 --branch v2026.8.3 https://github.com/NousResearch/hermes-agent
```

Every row cites a `file:line` in that checkout, or is explicitly marked
`UNVERIFIED` with the reason. Rows without a source were removed rather than
guessed. Where the v0.20.0 release notes disagree with the code, the code wins
and the discrepancy is called out.

> Runtime note: the release notes say "Node 26 required", and the container
> toolchain **is** pinned to Node 26 (`Dockerfile` node stage, below), but the
> app itself is a **Python** project driven by `uv`/Python 3.11 — the installer
> creates a Python 3.11 venv (`setup-hermes.sh:36`), and the runtime is Python
> (`pyproject.toml`, `uv.lock`). Node 26 is bundled for the JS toolchain, not as
> the language the agent runs in.

---

## 1. Config file: format, name, location

| Fact | Value | Source |
|---|---|---|
| Format / name | YAML, `config.yaml` | `hermes_cli/config.py:5`, `:1294-1299` |
| Default path | `$HERMES_HOME/config.yaml` (default `~/.hermes/config.yaml`; in Docker `/opt/data/config.yaml`) | `hermes_cli/config.py:696`, `:1294-1299` |
| Config is merged over `DEFAULT_CONFIG` | A partial `config.yaml` is valid; unspecified keys fall back to defaults | `hermes_cli/config_defaults.py:7` (`DEFAULT_CONFIG`) |
| Schema version marker | `_config_version: 33` in defaults | `hermes_cli/config_defaults.py:3125` |
| `${env:VAR}` SecretRef | Supported directly in `config.yaml`. `${env:NAME}` and bare `${NAME}` read `os.environ`. **Missing var → the literal placeholder is kept and a warning logged** (fails loud downstream, never silently blank) | `hermes_cli/config.py:2486-2531` |
| Non-env SecretRef sources (`vault:`, `bitwarden:`, `file:`) | NOT resolved inline in config.yaml — external backends inject env vars via the `secrets:` block, then you reference `${env:NAME}` | `hermes_cli/config.py:2519-2531` |

## 2. Top-level config sections used by this project

All from `hermes_cli/config_defaults.py` (`DEFAULT_CONFIG`, starts line 7):

| Section | Line | Purpose |
|---|---|---|
| `model` | 8 | Model id (string or mapping) |
| `providers` | 9 | Named custom endpoints |
| `toolsets` | 12 | Which toolsets/tools are enabled (default `["hermes-cli"]`) |
| `database` | 16 | SQLite journal mode etc. |
| `agent` | 31 | Incl. `agent.max_turns` (iteration cap) |
| `tool_output` | 525 | Incl. `tool_output.max_lines` (read_file cap) |
| `tool_loop_guardrails` | 534 | Per-turn tool loop caps |
| `compression` | 561 | Context compression |
| `approvals` | 2043 | Command/tool approval policy |
| `command_allowlist` | 2091 | Pre-approved dangerous shell-command globs |
| `hooks` | 2118 | Incl. `hooks.outbound` signed webhooks |
| `security` | 2131 | Security policy |
| `cron` | 2160 | Built-in scheduler settings |
| `logging` | 2379 | File logging level/rotation |
| `skills` | 1790 | Incl. `skills.external_dirs` |
| `gateway` | 2454 | Gateway daemon behavior (NOT platform tokens) |
| Per-platform: `slack` 1891, `discord` 1908, `whatsapp` 1996, `telegram` 2004, `mattermost` 2015, `matrix` 2023 | | Messaging platform config |

## 3. Approval / allowlist model

There is **no per-tool-name "only these tools" allowlist**. Access is controlled
by three separate mechanisms:

| Control | Key / default | Meaning | Source |
|---|---|---|---|
| Tool availability | `toolsets` (default `["hermes-cli"]`) | Which tools exist at all. `hermes-cli` = full CLI toolset | `config_defaults.py:12`; `toolsets.py:101` (`TOOLSETS`), `:463` |
| Approval mode | `approvals.mode` (default `"smart"`; valid `manual`/`smart`/`off`) | `off` = YOLO/full-allow — **do NOT use** | `config_defaults.py:2044`; `hermes_cli/approval_mode.py:16` |
| Cron approval mode | `approvals.cron_mode` (default `"deny"`) | In cron context, approval-required actions are denied (fail closed) | `config_defaults.py:2046` |
| Smart policy text | `approvals.smart_policy` (default `""`) | Extra operator rules appended to the smart-approval guardian prompt | `config_defaults.py:2053` |
| Consecutive-denial circuit breaker | `approvals.denial_breaker_threshold` (default `3`; `0` disables) | After N DENYs in a row → hard stop | `config_defaults.py:2060` |
| Deny globs | `approvals.deny` (default `[]`) | fnmatch globs blocked **before** any `--yolo`/`mode=off` bypass | `config_defaults.py:2070` |
| Pre-approved shell globs | `command_allowlist` (default `[]`) | Dangerous shell-command patterns permanently allowed | `config_defaults.py:2091`; `tools/approval.py:2494`, `:2528`, `:2551` |
| Subagent auto-approve (avoid) | `approvals.subagent_auto_approve` (default `False`) | Auto-approves dangerous cmds for subagents | `config_defaults.py:1726` |

Relevant toolset names (`toolsets.py` `TOOLSETS` keys): `web`, `search`,
`terminal`, `skills`, `browser`, `file`, `memory`, `delegation`,
`code_execution`, `cronjob`, `coding`, **`safe`** (= "Safe toolkit without
terminal access", includes `web`,`vision`,`image_gen`), `hermes-cli` (full).
Source: `toolsets.py:101-610`; `safe` at the `"safe"` entry; `hermes-cli` at `:463`.

## 4. Tool loop caps (release-note "session limits")

**UNVERIFIED as "session-wide".** The only `web_search` / `delegate_task` caps
in config are **per-turn**, and the counters reset every turn:

| Key | Default | Source |
|---|---|---|
| `tool_loop_guardrails.loop_caps.max_web_searches` | `50` (per turn; `0`=unlimited) | `config_defaults.py:555`; `agent/tool_guardrails.py:135,167` |
| `tool_loop_guardrails.loop_caps.max_subagents` | `50` (per turn; `0`=unlimited) | `config_defaults.py:558`; `agent/tool_guardrails.py:136,171` |

The v0.20.0 note's "session-wide caps on `web_search` and `delegate_task`" does
not match a session-scoped key in the schema — only per-turn caps exist.
`UNVERIFIED: no session-wide counter key found (searched config_defaults.py, tool_guardrails.py)`.

## 5. Iteration limit & read_file cap (release-note 90→500 / 500→2000)

| Key | Default | Source |
|---|---|---|
| `agent.max_turns` | `500` (main agent iteration cap) | `config_defaults.py:32` |
| `tool_output.max_lines` | `2000` (read_file pagination cap) | `config_defaults.py:527`, comment `:520-522` |
| `delegation.max_iterations` | `50` (subagent cap) | `config_defaults.py:1683` |

## 6. Compression

| Key | Default | Source |
|---|---|---|
| `compression.enabled` | `True` | `config_defaults.py:562` |
| `compression.threshold` | `0.50` (ratio) | `config_defaults.py:572` |
| `compression.threshold_tokens` | `None` (absolute token cap) | `config_defaults.py:577` |
| `compression.min_tail_user_messages` | `1` | `config_defaults.py:583` |
| `compression.model_thresholds` | `{}` (per-model ratio override, substring match) | `config_defaults.py:728` |

## 7. Paths to persist (Docker volume = whole `HERMES_HOME`)

| Path | Source |
|---|---|
| State root: `HERMES_HOME` env; default `~/.hermes`; win32 `%LOCALAPPDATA%\hermes` | `hermes_constants.py:53-74`; `hermes_cli/main.py:59` |
| Config: `$HERMES_HOME/config.yaml` | `hermes_constants.py:1294-1299` |
| Session DB (SQLite): `$HERMES_HOME/state.db` (+ `state.db-wal`, `state.db-shm`) | `hermes_state.py:244`, `:268`, `:1063` |
| Cron store: `$HERMES_HOME/cron/jobs.json`, output `$HERMES_HOME/cron/output/` | `cron/jobs.py:80-85` |
| Custom cron scripts: `$HERMES_HOME/scripts/` | `hermes_cli/subcommands/cron.py:51` |
| Skills: `$HERMES_HOME/skills/` | `hermes_constants.py:1302-1304` |
| Kanban DB: `$HERMES_HOME/kanban.db` | `hermes_cli/backup.py:994-995` |
| Logs: `$HERMES_HOME/logs/` | `config_defaults.py:2377` (comment) |

**Net: persist all of `HERMES_HOME`.** In the official Docker image
`HERMES_HOME=/opt/data` (`Dockerfile:378`), so the volume mounts at `/opt/data`.

## 8. Headless / non-interactive single run

| Fact | Value | Source |
|---|---|---|
| One-shot flag | `hermes -z "PROMPT"` (a.k.a. `--oneshot`) — prints only final response, then exits | `hermes_cli/_parser.py:102-114`; `hermes_cli/oneshot.py:170-192`; `hermes_cli/main.py:176-221` |
| ⚠ Approvals in oneshot | **Auto-bypassed** in `-z` mode ("approvals are auto-bypassed") — so `approvals.*` does NOT guard a oneshot run; only the enabled `toolsets` do | `hermes_cli/_parser.py:102-114` (help text) |
| Companion flags | `-m/--model`, `--provider` (needs `--model`), `-t/--toolsets`, `--usage-file PATH` | `_parser.py:115-125`; `oneshot.py:206-209` |
| No `--headless`/`--print`/`-p`-prompt | `-p` is `--profile` | `hermes_cli/main.py:589` |

## 9. Built-in scheduler (`hermes cron`)

Confirmed built-in. Subcommands (`hermes_cli/subcommands/cron.py`, dispatch
`hermes_cli/cron.py:463-504`): `list`, `create`(alias `add`), `edit`,
`pause`, `resume`, `run`, `remove`(`rm`/`delete`), `status`, `runs`/`history`,
`tick`.

`hermes cron create` flags (`hermes_cli/subcommands/cron.py:27-85`):

| Flag | Meaning |
|---|---|
| `schedule` (positional) | `'30m'`, `'every 2h'`, or cron `'0 9 * * *'` |
| `prompt` (positional, optional) | Self-contained task instruction |
| `--name` | Job name |
| `--deliver` | `origin`, `local`, `telegram`, `discord`, `signal`, or `platform:chat_id` |
| `--repeat` | Repeat count |
| `--skill` (repeatable) | Attach a skill |
| `--script` | Path under `$HERMES_HOME/scripts/`. Default: stdout injected into agent prompt. **With `--no-agent`: the script IS the job, stdout delivered verbatim.** `.sh`/`.bash` → bash, else Python |
| `--no-agent` | Skip the LLM; run `--script` on schedule, deliver stdout directly. Empty stdout = silent |
| `--workdir` | Absolute cwd + injects AGENTS.md/CLAUDE.md from there |
| `--model` / `--provider` | Pin model for the job |

Firing: default in-process 60s ticker driven by the gateway / `hermes cron
tick`; scheduler code in `cron/scheduler.py` (`tick()` at `:4113`). Hosted
scale-to-zero uses **Chronos managed-cron** (`docs/chronos-managed-cron-contract.md:1-40`).
Jobs stored in `$HERMES_HOME/cron/jobs.json` (`cron/jobs.py:84-85`).

## 10. Outbound webhook (signed, HMAC)

Implementation `agent/outbound_webhooks.py`; docs
`website/docs/user-guide/features/hooks.md:1512-1596`.

| Fact | Value | Source |
|---|---|---|
| Configured via | `hooks.outbound:` **list in `config.yaml`** (not a CLI command) | `agent/outbound_webhooks.py:156`; `cli.py:1053-1057`; `gateway/run.py:10857-10860` |
| Per-target keys | `url` (req, http/https), `events` (req, non-empty, validated vs `VALID_HOOKS`), `secret_env` (preferred) or `secret`, `matcher` (regex, only for `pre_tool_call`/`post_tool_call`), `timeout` (1–60s), `name` | `agent/outbound_webhooks.py:32-44`, `:268-355`, `:358-373` |
| Conventional secret var | `HERMES_OUTBOUND_WEBHOOK_SECRET` (any name works via `secret_env`) | `agent/outbound_webhooks.py:39`; `hooks.md:1533` |
| Signature header | **`X-Hermes-Signature-256: sha256=<hexdigest>`** (GitHub-style) | `agent/outbound_webhooks.py:443-447` |
| Algorithm / signed data | HMAC-SHA256 over the **raw JSON POST body** | `agent/outbound_webhooks.py:404-431`, `:443-447` |
| Other headers | `Content-Type: application/json`, `User-Agent: Hermes-Agent-Outbound-Webhook`, `X-Hermes-Event`, `X-Hermes-Delivery` | `agent/outbound_webhooks.py:437-442` |
| Replay protection | `delivery_id` + `timestamp` inside signed body; dedupe on delivery id, reject stale ts | `hooks.md:1582-1585`; `agent/outbound_webhooks.py:411-412` |
| Delivery semantics | fire-and-forget queue (max 256), 1 worker, `MAX_DELIVERY_ATTEMPTS=2`, retry on conn err/5xx, no retry on 4xx, redirects never followed | `agent/outbound_webhooks.py:91-93`, `:476-479`, `:504-569` |
| Disable switch | `HERMES_SAFE_MODE=1` skips registration | `agent/outbound_webhooks.py:171-173` |
| Channel enumeration | `hermes send --list` (optional platform filter). `hermes send -t platform[:chat_id]` sends a message reusing gateway creds, no LLM | `hermes_cli/send_cmd.py:461-468`, `:386-430` |

Receiver verification (from docs `hooks.md:1574-1580`):

```python
import hashlib, hmac
def verify(body: bytes, header: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)
```

> Scope note: `hooks.outbound` events are **agent lifecycle events**
> (`on_session_end`, `subagent_stop`, `post_tool_call`, …), not an arbitrary
> "post this report body" channel. A `--no-agent` cron job may not emit an
> agent-session lifecycle event, so use the webhook for *run/lifecycle
> notification* and deliver *report content* via `--deliver` (local/platform)
> or the script's stdout. See `docs/UNVERIFIED.md`.

## 11. Model provider config + API-key env vars

- Set model via `model.default` (or `model.model`) + `model.provider`
  (`cli-config.yaml.example:24-64`; comment at `:26`). `model.provider` default
  `"auto"`. Optional `model.base_url`, `model.api_key`.
- Providers read their **own** API-key env var (from
  `plugins/model-providers/*/__init__.py` `env_vars=` tuples):

| Provider | Env var(s) | Source |
|---|---|---|
| anthropic | `ANTHROPIC_API_KEY`, `ANTHROPIC_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN` | `plugins/model-providers/anthropic/__init__.py:48` |
| openrouter | `OPENROUTER_API_KEY` (also accepts `OPENAI_API_KEY` fallback) | `.../openrouter/__init__.py:197`; `cli-config.yaml.example:31` |
| nous (Portal) | `NOUS_API_KEY` | `.../nous/__init__.py:75` |
| gemini/google | `GOOGLE_API_KEY`, `GEMINI_API_KEY` | `.../gemini/__init__.py:55` |
| deepseek | `DEEPSEEK_API_KEY` | `.../deepseek/__init__.py:90` |
| xai | `XAI_API_KEY` | `.../xai/__init__.py:11` |
| zai (GLM) | `GLM_API_KEY`, `ZAI_API_KEY`, `Z_AI_API_KEY` | `.../zai/__init__.py:114` |

- OpenAI: **no standalone `openai` provider plugin.** `OPENAI_API_KEY` is read
  only when the resolved endpoint is an OpenAI/Azure-OpenAI URL (host-gated),
  `hermes_cli/runtime_provider.py:1081,1143,1249,1270`. Use OpenRouter or Nous
  Portal for a turnkey path.

## 12. Logging

| Key | Default | Source |
|---|---|---|
| `logging.level` | `"INFO"` (DEBUG/INFO/WARNING) | `config_defaults.py:2380` |
| `logging.max_size_mb` | `5` | `config_defaults.py:2381` |
| `logging.backup_count` | `3` | `config_defaults.py:2382` |

Destination is fixed to `$HERMES_HOME/logs/` (agent.log INFO+, errors.log
WARNING+) — no arbitrary path key. `UNVERIFIED: no configurable log directory key`.

## 13. Skills structure

- Layout: `skills/<category>/<skill-name>/SKILL.md` (+ optional `scripts/`,
  `references/`). A directory is a skill root iff it contains `SKILL.md`.
  Source: `agent/skill_utils.py:146`; `website/docs/.../creating-skills.md:25-42`.
- `SKILL.md` = YAML frontmatter + markdown body. **Required fields: `name`,
  `description`.** Optional: `version`, `author`, `license`, `platforms`,
  `metadata.hermes.{tags,related_skills,requires_toolsets,requires_tools,config,blueprint}`,
  `required_environment_variables`. Source: `creating-skills.md:44-79`;
  `agent/skill_utils.py:174-220`.
- `metadata.hermes.blueprint.schedule` makes a skill a runnable automation.
- Discovery: default `$HERMES_HOME/skills/` (`hermes_constants.py:1302-1304`);
  extra dirs via **`skills.external_dirs`** config (`~`/`${VAR}` expanded,
  relatives resolved against `HERMES_HOME`) — `agent/skill_utils.py:483-521`,
  `:566-573`.

Real example (`skills/github/github-auth/SKILL.md:1-12`):

```yaml
---
name: github-auth
description: "GitHub auth setup: HTTPS tokens, SSH keys, gh CLI login."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Authentication, Git, gh-cli, SSH, Setup]
    related_skills: [github-pr-workflow]
---
```

## 14. Docker

| Fact | Value | Source |
|---|---|---|
| Official published image | **`nousresearch/hermes-agent`** (Docker Hub), multi-arch amd64+arm64 | `.github/workflows/docker.yml:27`, `:38-48`, `:216-217`, `:261-264` |
| Release tag image | `nousresearch/hermes-agent:v2026.8.3` (also `:latest`, `:main`) | `.github/workflows/docker.yml:261-264` |
| Runtime base | `debian:13.4`; toolchain stages use `node:26-bookworm-slim` and `ghcr.io/astral-sh/uv:0.11.6-python3.13` | `Dockerfile:52`, `:43`, `:51`, comment `:46` |
| Container env | `HERMES_HOME=/opt/data`, `HERMES_WRITE_SAFE_ROOT=/opt/data`, `HERMES_DISABLE_LAZY_INSTALLS=1` | `Dockerfile:378-380` |
| Entrypoint | s6-overlay `/init` runs `/etc/cont-init.d/*` (lexical order) then execs the CMD as hermes args | `Dockerfile:434-435`; `docker/main-wrapper.sh:16-19` |
| Existing cont-init scripts | `01-hermes-setup` (→ `stage2-hook.sh`), `015-supervise-perms`, `02-reconcile-profiles` | `Dockerfile:352-357` |
| Config/`.env` seeding | On first boot only, if absent: `config.yaml`←`cli-config.yaml.example`, `.env`←`.env.example` | `docker/stage2-hook.sh:418-431` |
| Compose | services `gateway` (`command: ["gateway","run"]`) + `dashboard`; volume `~/.hermes:/opt/data`; `HERMES_UID/GID` remap | `docker-compose.yml:31-76` |
| Shell installer | `setup-hermes.sh` — Python 3.11 venv via `uv`, symlinks `hermes` CLI | `setup-hermes.sh:1-70` |

## 15. LINE / gateway placeholder

- LINE is a recognized gateway platform (binds a webhook port) but has **no
  `line:` section in `DEFAULT_CONFIG`** and no `LINE_*` var in `.env.example`;
  its credentials are handled by the gateway layer. Source:
  `gateway/config.py:393` (`PORT_BINDING_PLATFORM_VALUES`); absence verified in
  `config_defaults.py` / `.env.example`.
- Per-platform config lives under a **top-level** platform key (e.g. `slack:`),
  NOT under `gateway:`; tokens live in `$HERMES_HOME/.env`
  (`SLACK_BOT_TOKEN`, `TELEGRAM_BOT_TOKEN`, …). Source: `config_defaults.py:1891`;
  `.env.example:347-359`.
- `UNVERIFIED: exact LINE config/env keys` — not in DEFAULT_CONFIG; would need
  the gateway LINE setup wizard (`hermes gateway setup`) in env B.
