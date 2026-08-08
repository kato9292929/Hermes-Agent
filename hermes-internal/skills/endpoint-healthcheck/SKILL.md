---
name: endpoint-healthcheck
description: "Probe configured HTTP endpoints (status, latency, required JSON fields), understand x402 402 gates as healthy, and emit a JSON + markdown health report."
version: 1.0.0
author: Internal
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Monitoring, HTTP, Healthcheck, x402, DailyReport, Ops]
    requires_tools: [terminal]
---

# Endpoint health check

Probe a list of internal/product HTTP endpoints and produce a structured health
report. This is use case #1 of the internal agent: endpoint reachability checks
and a daily report.

## What it checks (per target)

- HTTP status code vs an expected status (`expect_status`, default `200`)
- Response time (ms)
- Presence of required fields in a JSON response body (`expect_json_fields`,
  dotted paths like `data.version`)

## x402 payment-gated endpoints

A `402 Payment Required` response is **not** an error when the target declares
`expect_status: 402`. It is the expected, healthy signal that the paywall is
live. Payment execution is out of scope for this skill — we only assert the gate
responds as designed.

## Targets are external to this skill

Targets are **never** hardcoded. They live in `targets.yaml` next to this file
(schema in `targets.example.yaml`). The shipped `targets.yaml` is empty on
purpose; fill it in for your deployment. Supported keys: `name`, `url`,
`method`, `headers`, `body`, `timeout_seconds`, `expect_status`,
`expect_json_fields`.

## How to run it

The runner is `scripts/run_healthcheck.py` (standard library + PyYAML only). It
prints a markdown report to stdout and can also write JSON and markdown files.

```bash
python3 skills/endpoint-healthcheck/scripts/run_healthcheck.py \
  --targets skills/endpoint-healthcheck/targets.yaml \
  --json-out /opt/data/cron/output/healthcheck.json \
  --md-out   /opt/data/cron/output/healthcheck.md
```

In the container, this skill is installed at `$HERMES_HOME/skills/endpoint-healthcheck/`
(i.e. `/opt/data/skills/endpoint-healthcheck/`), and a bash wrapper suitable for
the built-in scheduler is installed at `$HERMES_HOME/scripts/healthcheck.sh`
(see `scripts/healthcheck.sh` in the repo).

### Deterministic daily run (primary path — no LLM)

The daily report runs WITHOUT the agent loop, so it is deterministic and needs
no tool approvals:

```bash
hermes cron create "0 9 * * *" \
  --name endpoint-healthcheck-daily \
  --script healthcheck.sh \
  --no-agent \
  --deliver local
```

(`scripts/register-cron.sh` does this idempotently.)

### Agent-driven run (optional)

If a profile enables the `terminal` toolset, the agent can run the runner
itself on request ("check the endpoints"). Under the default `safe` toolset the
agent has no terminal access, so use the deterministic path above.

## Failure semantics — no swallowing

- Unreachable hosts and unexpected statuses are recorded in the report **as
  anomalies** (this is the required reporting behavior) and force a non-zero
  exit code (`2`). They are never turned into a fake success.
- A misconfiguration (missing/unreadable `targets.yaml`, invalid YAML, unknown
  target keys) crashes loudly with a traceback — it is not caught.
- An empty target list exits with code `3` ("No targets configured") so the
  empty state is visible rather than mistaken for success.

## Output

- **stdout**: markdown report (delivered verbatim by `--no-agent` cron).
- **JSON**: full structured result — summary counts plus per-target
  `status_code`, `response_time_ms`, `ok`, `anomalies`, `checked_fields`.
  Written to `--json-out` if given, else emitted on stderr.
