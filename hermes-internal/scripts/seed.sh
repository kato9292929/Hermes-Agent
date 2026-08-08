#!/usr/bin/env sh
# shellcheck shell=sh
# Shared seed logic: copy this deployment's config-as-code, skill, and cron
# script from the immutable image tree (/opt/hermes-internal) onto the
# HERMES_HOME data volume, and drop a marker recording which config version was
# applied.
#
# Idempotent. Callable in two contexts:
#   * as root, from docker/cont-init.d/03-hermes-internal-seed (PID-1 boot path)
#   * as the hermes user, from scripts/entrypoint.sh (covers the non-PID-1 path
#     where cont-init does not run — see UNVERIFIED #3)
# chown is attempted only when running as root; otherwise it is skipped because
# the files are already owned by the runtime user.
#
# Overwrite policy:
#   config.yaml, SKILL.md, targets.example.yaml, run_healthcheck.py,
#   healthcheck.sh   -> overwritten every call (config-as-code)
#   targets.yaml     -> seeded ONLY if absent (preserve operator edits)
set -eu

HERMES_HOME="${HERMES_HOME:-/opt/data}"
SRC="${HERMES_INTERNAL_SRC:-/opt/hermes-internal}"
uid="${HERMES_UID:-10000}"
gid="${HERMES_GID:-10000}"

skill_dir="$HERMES_HOME/skills/endpoint-healthcheck"
marker="$HERMES_HOME/.hermes-internal-seeded"

mkdir -p "$skill_dir/scripts" "$HERMES_HOME/scripts"

# config-as-code (overwrite)
cp "$SRC/config/config.yaml" "$HERMES_HOME/config.yaml"

# skill runner + docs (overwrite)
cp "$SRC/skills/endpoint-healthcheck/SKILL.md"             "$skill_dir/SKILL.md"
cp "$SRC/skills/endpoint-healthcheck/targets.example.yaml" "$skill_dir/targets.example.yaml"
cp "$SRC/skills/endpoint-healthcheck/scripts/run_healthcheck.py" "$skill_dir/scripts/run_healthcheck.py"

# targets.yaml — seed only if missing (preserve operator edits on the volume)
if [ ! -f "$skill_dir/targets.yaml" ]; then
    cp "$SRC/skills/endpoint-healthcheck/targets.yaml" "$skill_dir/targets.yaml"
fi

# cron script (looked up by `hermes cron ... --script` under $HERMES_HOME/scripts/)
cp "$SRC/scripts/healthcheck.sh" "$HERMES_HOME/scripts/healthcheck.sh"
chmod 0755 "$HERMES_HOME/scripts/healthcheck.sh"

# Marker (a visible trace): record the sha256 of the config we just applied.
# entrypoint.sh compares this against the source to detect a stale/absent seed.
cfg_hash="$(sha256sum "$SRC/config/config.yaml" | cut -d' ' -f1)"
printf '%s\n' "$cfg_hash" > "$marker"

# Ownership so the unprivileged hermes user can read/write. Root only.
if [ "$(id -u)" = "0" ]; then
    chown -R "$uid:$gid" \
        "$HERMES_HOME/config.yaml" "$skill_dir" \
        "$HERMES_HOME/scripts/healthcheck.sh" "$marker" 2>/dev/null \
        || echo "[seed] warning: chown skipped (rootless?) — continuing"
fi

echo "[seed] applied config $cfg_hash to $HERMES_HOME"
