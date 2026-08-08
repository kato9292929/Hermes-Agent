#!/usr/bin/env sh
# shellcheck shell=sh
# Container entrypoint wrapper (the image CMD).
#
# Purpose: guarantee this deployment's config-as-code is actually applied before
# the agent starts — on EVERY start path, including non-PID-1 platforms where
# the s6 cont-init seed hook does not run (UNVERIFIED #3). The failure mode we
# refuse to allow is "started silently with the base image's DEFAULT config".
#
# Steps:
#   1. Run the shared, idempotent seed (safe even if cont-init already ran).
#   2. Verify the applied $HERMES_HOME/config.yaml byte-for-byte matches the
#      image's intended config. If it does NOT, abort loudly — do not start.
#   3. exec the requested hermes command (default: gateway run).
#
# No fallback to default config; a mismatch is a hard failure by design.
set -eu

HERMES_HOME="${HERMES_HOME:-/opt/data}"
SRC="${HERMES_INTERNAL_SRC:-/opt/hermes-internal}"

# 1. Seed (idempotent). Runs as the current user; seed.sh skips chown if non-root.
"$SRC/scripts/seed.sh"

# 2. Verify the applied config matches the intended config exactly.
applied_cfg="$HERMES_HOME/config.yaml"
intended_cfg="$SRC/config/config.yaml"

if [ ! -f "$applied_cfg" ]; then
    echo "FATAL: $applied_cfg is missing after seeding — refusing to start." >&2
    exit 70
fi

want="$(sha256sum "$intended_cfg" | cut -d' ' -f1)"
have="$(sha256sum "$applied_cfg" | cut -d' ' -f1)"

if [ "$want" != "$have" ]; then
    echo "FATAL: applied config does not match this image's intended config." >&2
    echo "       intended ($intended_cfg): $want" >&2
    echo "       applied  ($applied_cfg): $have" >&2
    echo "       The config-as-code seed did not take. Refusing to start with" >&2
    echo "       the wrong (possibly default) configuration." >&2
    exit 71
fi

echo "[entrypoint] config verified ($have); starting: hermes ${*:-<default>}"

# 3. Hand off to hermes. With no args, start the resident gateway.
if [ "$#" -eq 0 ]; then
    set -- gateway run
fi
exec hermes "$@"
