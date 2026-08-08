# hermes-internal

An internal single-agent deployment of [Hermes Agent](https://github.com/NousResearch/hermes-agent)
(Nous Research, v0.20.0 / tag `v2026.8.3`, MIT) that runs resident on Railway in
Docker. It ships one working capability — **endpoint health checks with a daily
report** (use case #1) — on a structure that lets the other three planned use
cases (periodic batches, research sub-tasking, an internal Q&A gateway) be added
later as sibling skills under `skills/`.

This repository is **config-as-code**: the Hermes config, the skill, and the
cron script are baked into the image and seeded onto the persistent volume at
boot. Secrets are never stored in the repo — they are `${env:VAR}` references
resolved from environment variables.

Everything is built strictly against the real upstream source. Facts (with
`file:line` citations) are in [`docs/hermes-facts.md`](docs/hermes-facts.md);
anything that could not be verified end-to-end in the sandbox is listed in
[`docs/UNVERIFIED.md`](docs/UNVERIFIED.md).

## Layout

```
hermes-internal/
  Dockerfile                     # FROM nousresearch/hermes-agent:v2026.8.3 + our payload
  docker-compose.yml             # local verification
  railway.json                   # Railway build config
  config/
    config.yaml                  # active config (partial; merged over defaults)
    config.example.yaml          # annotated superset (webhook + gateway shown)
  skills/
    endpoint-healthcheck/
      SKILL.md                   # runbook
      targets.yaml               # real targets (shipped EMPTY)
      targets.example.yaml       # target schema
      scripts/run_healthcheck.py # the probe (stdlib + PyYAML)
  scripts/
    healthcheck.sh               # deterministic --no-agent cron runner
    run-once.sh                  # ad-hoc `hermes -z` single run
    register-cron.sh             # idempotently register the daily job
  docker/
    cont-init.d/03-hermes-internal-seed  # boot-time seed hook
  docs/
    hermes-facts.md              # upstream facts w/ citations
    UNVERIFIED.md                # unverified items
  .env.example
```

## What the agent does (today)

- Reads a list of HTTP endpoints from `skills/endpoint-healthcheck/targets.yaml`.
- Checks each: HTTP status vs expected, response time, and required JSON fields.
- Treats an x402 `402 Payment Required` as **healthy** when the target declares
  `expect_status: 402` (payment execution is out of scope).
- Emits a structured JSON result and a markdown report.
- Runs daily via the built-in Hermes scheduler as a deterministic, no-LLM job.

Failures are never swallowed: unreachable/unexpected responses are reported as
anomalies with a non-zero exit code; misconfiguration crashes loudly; an empty
target list is a visible, distinct outcome (exit 3).

## Environment variables

Only variables this deployment actually reads. Full copy in `.env.example`.

| Variable | Required | Read by | Purpose |
|---|---|---|---|
| `HERMES_MODEL` | ✅ | `config.yaml` `model.default` | Model id (provider-specific) |
| `HERMES_MODEL_PROVIDER` | ✅ | `config.yaml` `model.provider` | `openrouter` / `nous` / `anthropic` / `auto` |
| One provider key, e.g. `OPENROUTER_API_KEY` / `NOUS_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | ✅ (the one matching the provider) | provider plugin | Model API auth. See `docs/hermes-facts.md` §11 |
| `HERMES_OUTBOUND_WEBHOOK_URL` | optional | `config.yaml` `hooks.outbound` | Signed webhook target (if enabled) |
| `HERMES_OUTBOUND_WEBHOOK_SECRET` | optional | `config.yaml` `hooks.outbound.secret_env` | HMAC-SHA256 secret (if enabled) |
| `HEALTHCHECK_SCHEDULE` | optional | `scripts/register-cron.sh` | Cron spec (default `0 9 * * *`) |
| `HEALTHCHECK_DELIVER` | optional | `scripts/register-cron.sh` | Cron delivery target (default `local`) |
| `HERMES_UID` / `HERMES_GID` | optional | Docker/compose | Container user remap (default 10000) |

Do **not** set `HERMES_HOME` — the image fixes it to `/opt/data` (the volume).

## Run locally

```bash
cp .env.example .env         # fill in HERMES_MODEL, HERMES_MODEL_PROVIDER, provider key
docker compose up --build
```

Then, once up:

```bash
# add real endpoints
docker compose exec hermes sh -c 'vi /opt/data/skills/endpoint-healthcheck/targets.yaml'
# register + run the daily job now to test
docker compose exec hermes bash /opt/hermes-internal/scripts/register-cron.sh
docker compose exec hermes hermes cron run endpoint-healthcheck-daily
docker compose exec hermes cat /opt/data/cron/output/healthcheck.md
```

Run the probe directly (no scheduler), useful for a quick check:

```bash
docker compose exec hermes python3 \
  /opt/data/skills/endpoint-healthcheck/scripts/run_healthcheck.py \
  --targets /opt/data/skills/endpoint-healthcheck/targets.yaml
```

## Deploy to Railway

1. **Create a service from this repo.** `railway.json` selects the Dockerfile
   builder; the image's default CMD runs `hermes gateway run` (resident gateway
   + built-in scheduler).
2. **Add a Volume** mounted at **`/opt/data`** (this is `HERMES_HOME` — it holds
   `config.yaml`, `state.db`, `cron/`, `skills/`, `logs/`). Without it, all state
   is lost on every redeploy.
3. **Set Variables** (service → Variables): `HERMES_MODEL`,
   `HERMES_MODEL_PROVIDER`, and the matching provider key. Optionally the webhook
   and `HEALTHCHECK_*` variables.
4. **Fill in targets.** Either edit `skills/endpoint-healthcheck/targets.yaml`
   in the repo and redeploy (they seed to the volume only if not already
   present), or edit `/opt/data/skills/endpoint-healthcheck/targets.yaml` on the
   volume directly.
5. **Register the daily job** once (Railway shell or a one-off):
   `bash /opt/hermes-internal/scripts/register-cron.sh`. The resident gateway's
   60-second ticker fires it on schedule.

> Config-as-code: `config.yaml` and the skill files are re-seeded from the image
> on every boot (except `targets.yaml`, seeded only if absent). Change config in
> the repo and redeploy — do not edit `config.yaml` on the volume.

See [`docs/UNVERIFIED.md`](docs/UNVERIFIED.md) for what still needs validating in
a real Railway/keyed environment (items #1–#5, #14 are the deploy path).

## Notifications

The daily report is written to `/opt/data/cron/output/` and delivered per the
cron `--deliver` target (default `local`). A **signed outbound webhook**
(`hooks.outbound`, HMAC-SHA256, header `X-Hermes-Signature-256`) is the intended
first-choice notification channel and is pre-wired but commented out — enable it
by setting `HERMES_OUTBOUND_WEBHOOK_URL` + `HERMES_OUTBOUND_WEBHOOK_SECRET` and
uncommenting the `hooks.outbound` block in `config/config.yaml`. Note the scope
caveat in `docs/UNVERIFIED.md` #12: the webhook carries agent lifecycle events,
not arbitrary report bodies. Receiver implementation is out of scope.

## Security posture

- **No terminal for the LLM.** `toolsets: ["safe"]` (upstream "Safe toolkit
  without terminal access"). The agent cannot run shell, execute code, or
  delegate tasks.
- **Approvals, not YOLO.** `approvals.mode: manual` (never `off`),
  `approvals.cron_mode: deny` (fail closed in cron), a consecutive-denial
  circuit breaker, and `approvals.deny` globs that block dangerous commands
  before any bypass. `command_allowlist` is empty.
- **Deterministic daily job.** The health check runs via `--no-agent` (no LLM,
  no tool-approval surface, no oneshot approval-bypass concern).
- **Secrets via env only.** `${env:VAR}` references; `.env` is git-ignored.
- Once history accumulates, run `hermes approvals suggest` to review a
  data-driven allowlist (needs prior runs; not usable on first boot).

## Adding the other use cases (2–4)

Each future capability is a new skill directory — no image surgery:

1. `mkdir -p skills/<new-skill>/scripts` and add a `SKILL.md` with YAML
   frontmatter (required: `name`, `description`; see the upstream template in
   `docs/hermes-facts.md` §13 and the existing `endpoint-healthcheck` skill).
2. Add the skill's files to the boot seed hook
   (`docker/cont-init.d/03-hermes-internal-seed`) so they land on the volume,
   or set `skills.external_dirs` in `config.yaml` to load an extra directory.
3. For a scheduled skill, add a `hermes cron create ...` line (mirror
   `scripts/register-cron.sh`). For an interactive/gateway skill (use case #4,
   e.g. LINE), configure the platform via `hermes gateway setup` and add the
   per-platform top-level block to `config.yaml` (see `config.example.yaml`).
4. If a skill needs tools beyond `safe` (e.g. `terminal`, `web`), widen
   `toolsets` deliberately and keep the approval posture in mind.

## Unverified items

This repo is complete as source. Items requiring keys/network/Railway to confirm
are tracked in [`docs/UNVERIFIED.md`](docs/UNVERIFIED.md). Code and docs that
depend on an unverified fact carry an inline `UNVERIFIED:` note.
