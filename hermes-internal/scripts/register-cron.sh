#!/usr/bin/env bash
# Idempotently register the daily endpoint health check with the built-in Hermes
# scheduler. Run this ONCE after the gateway is up (environment B), or any time
# you change the schedule.
#
# The job runs scripts/healthcheck.sh with --no-agent (no LLM), delivering the
# markdown report verbatim to the chosen target.
#
# Env overrides:
#   HEALTHCHECK_SCHEDULE  cron/interval spec (default "0 9 * * *")
#   HEALTHCHECK_DELIVER   delivery target (default "local"; also origin,
#                         telegram, discord, signal, or platform:chat_id)
set -euo pipefail

SCHEDULE="${HEALTHCHECK_SCHEDULE:-0 9 * * *}"
DELIVER="${HEALTHCHECK_DELIVER:-local}"
NAME="endpoint-healthcheck-daily"

# UNVERIFIED: `hermes cron list` output format not confirmed in environment A,
# so this name-grep idempotency check is heuristic. If it misfires, remove the
# job with `hermes cron remove $NAME` and re-run.
if hermes cron list --all 2>/dev/null | grep -q "$NAME"; then
    echo "cron job '$NAME' already registered; nothing to do"
    exit 0
fi

hermes cron create "$SCHEDULE" \
    --name "$NAME" \
    --script healthcheck.sh \
    --no-agent \
    --deliver "$DELIVER"

echo "registered cron job '$NAME' (schedule: '$SCHEDULE', deliver: '$DELIVER')"
