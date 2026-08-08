#!/usr/bin/env bash
# Deterministic endpoint health check for the built-in Hermes scheduler.
#
# Designed to be registered with `hermes cron create ... --script healthcheck.sh
# --no-agent`, which runs this script on schedule with NO LLM and delivers its
# stdout verbatim. That makes the daily report deterministic and free of any
# tool-approval / oneshot-bypass surface.
#
# It runs the skill's Python runner against the deployment's targets.yaml,
# writes JSON + markdown into the cron output dir, and prints the markdown to
# stdout. Exit code propagates (0 ok / 2 anomalies / 3 no targets) so failures
# are never hidden.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-/opt/data}"
SKILL_DIR="$HERMES_HOME/skills/endpoint-healthcheck"
RUNNER="$SKILL_DIR/scripts/run_healthcheck.py"
TARGETS="$SKILL_DIR/targets.yaml"
OUT_DIR="$HERMES_HOME/cron/output"

mkdir -p "$OUT_DIR"

if [ ! -f "$RUNNER" ]; then
    echo "healthcheck: runner not found at $RUNNER" >&2
    exit 1
fi

# Capture the runner's exit code without letting `set -e` abort first.
set +e
python3 "$RUNNER" \
    --targets "$TARGETS" \
    --json-out "$OUT_DIR/healthcheck.json" \
    --md-out "$OUT_DIR/healthcheck.md"
rc=$?
set -e

# Exit code 3 (no targets) prints only to stderr, leaving stdout blank — which
# --no-agent would treat as "silent". Surface it on stdout so it is visible.
if [ "$rc" -eq 3 ]; then
    echo "# Endpoint health report — NO TARGETS CONFIGURED"
    echo
    echo "targets.yaml is empty. Add endpoints (see targets.example.yaml)."
fi

exit "$rc"
