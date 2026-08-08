#!/usr/bin/env bash
# Run the agent ONCE, non-interactively, and print only the final response.
#
# Wraps `hermes -z` (a.k.a. --oneshot). Intended for ad-hoc scripted prompts and
# for external schedulers (e.g. a Railway cron) that prefer not to keep a
# resident process.
#
# WARNING: `hermes -z` AUTO-BYPASSES approvals (docs/hermes-facts.md §8). In
# oneshot mode the enabled `toolsets` are the ONLY guard — this deployment uses
# the `safe` toolset (no terminal), which is what keeps oneshot safe. Do not
# widen toolsets for oneshot use without understanding this.
#
# For the deterministic endpoint health check, use scripts/healthcheck.sh
# instead (no LLM, no bypass).
set -euo pipefail

if [ "$#" -eq 0 ]; then
    echo "usage: run-once.sh \"<prompt>\"" >&2
    echo "  for the endpoint health check, use scripts/healthcheck.sh" >&2
    exit 64
fi

exec hermes -z "$*"
