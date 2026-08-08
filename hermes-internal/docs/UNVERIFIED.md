# Unverified items

Everything here was implemented against the upstream source (see
`docs/hermes-facts.md`) but could **not** be exercised end-to-end in environment
A (no model API key, no messaging credentials, no registry pull, no Railway
project). Each row: what is unverified / why / what is needed to verify / where
to fix after verifying.

Environment A = sandbox (file generation, YAML/JSON syntax, Python-logic tests,
Dockerfile structure). Environment B = keys + network + registry + Railway.

| # | Item | Why unverified | How to verify (env B) | What to fix after verifying |
|---|---|---|---|---|
| 1 | Docker image builds | Base image `nousresearch/hermes-agent:v2026.8.3` must be pulled from Docker Hub; not available in env A | `docker build -t hermes-internal .` | `Dockerfile` (base tag / COPY paths) if build fails |
| 2 | Container boots & `hermes --version` | Requires a successful build + run | `docker compose up --build`; `docker compose exec hermes hermes --version` | `Dockerfile`, `docker-compose.yml` |
| 3 | cont-init seed hook runs | `/etc/cont-init.d/*` only run on the s6 PID-1 path. On non-PID-1 platforms (`docker run --init`, Fly Machines) the dispatcher falls back and may skip it | `docker compose exec hermes cat /opt/data/config.yaml` and confirm it is OUR config, not the default | `docker/cont-init.d/03-hermes-internal-seed`; if the platform is non-PID-1, move seeding into a CMD wrapper script |
| 4 | config.yaml is accepted / merges cleanly | Needs the running runtime to parse + migrate it | `docker compose exec hermes hermes config get toolsets` (expect `["safe"]`) | `config/config.yaml` |
| 5 | Model wiring (id + provider + key) | No API key in env A; `${env:HERMES_MODEL}` left literal | Set `HERMES_MODEL`, `HERMES_MODEL_PROVIDER`, provider key; `hermes -z "say hi"` | `config/config.yaml` model block; `.env.example`; README env table |
| 6 | `${env:VAR}` resolution in config | Depends on runtime env expansion at load | `hermes config get model` and confirm the values resolved | `config/config.yaml` |
| 7 | `safe` toolset really excludes terminal at runtime | Static definition read from `toolsets.py`; not run | `hermes -z "run: echo hi in a shell"` should refuse/lack the tool | `config/config.yaml` toolsets |
| 8 | Approvals posture (manual / cron_mode deny / deny globs) | No agent run to trigger an approval | Trigger an approval-required action in a gateway session | `config/config.yaml` approvals block |
| 9 | Built-in cron registration | `hermes cron` needs the runtime; list output format unconfirmed → name-grep idempotency is heuristic | `bash scripts/register-cron.sh` then `hermes cron list` | `scripts/register-cron.sh` (idempotency check) |
| 10 | `--no-agent --script healthcheck.sh` delivery | Needs a scheduled run in the container | `hermes cron run endpoint-healthcheck-daily`; inspect `/opt/data/cron/output/` | `scripts/healthcheck.sh`; SKILL.md |
| 11 | Outbound webhook signing/delivery | Receiver + secret required; block is commented off by default | Set URL+secret, uncomment `hooks.outbound`, verify `X-Hermes-Signature-256` at the receiver | `config/config.yaml` hooks block |
| 12 | Webhook carries report CONTENT | `hooks.outbound` sends lifecycle events, not arbitrary report bodies; a `--no-agent` job may emit none | Observe payloads at the receiver during a run | Consider delivering report content via `--deliver` (platform) instead; SKILL.md / README |
| 13 | web_search / delegate_task "session-wide" caps | No such session-scoped key exists upstream; only per-turn caps | Inspect `tool_loop_guardrails` behavior across turns | `config/config.yaml` (keys are correct as per-turn; wording only) |
| 14 | Railway deploy (build, volume, cron, variables) | No Railway project in env A; `railway.json` schema not validated live | Create a Railway service from this repo, add a volume mounted at `/opt/data`, set Variables | `railway.json`; README Railway section |
| 15 | LINE / messaging gateway keys | No `line:` section in DEFAULT_CONFIG; handled by the gateway layer | `hermes gateway setup` (LINE) in env B | `config/config.example.yaml` gateway placeholder |
| 16 | Node 26 requirement vs Python runtime | Release notes say "Node 26 required"; repo is a Python/uv app that bundles Node 26 for its toolchain | Inspect the running image (`node --version`, `python --version`) | Doc note in `docs/hermes-facts.md` only |
