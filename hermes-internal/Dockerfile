# Internal Hermes agent image.
#
# Based on the OFFICIAL published image (Docker Hub: nousresearch/hermes-agent),
# pinned to the v0.20.0 release tag. We do NOT rebuild Hermes or its toolchain
# (Node 26 / uv / Python) — we only add this deployment's config-as-code, the
# endpoint-healthcheck skill, the cron script, and a boot-time seed hook.
#
# UNVERIFIED: `docker build` was not executed in environment A (pulling the base
# image needs registry/network access). Dockerfile is structurally validated
# only. See docs/UNVERIFIED.md.
FROM nousresearch/hermes-agent:v2026.8.3

LABEL org.opencontainers.image.title="hermes-internal" \
      org.opencontainers.image.description="Internal Hermes agent (endpoint healthcheck + daily report)" \
      org.opencontainers.image.base.name="docker.io/nousresearch/hermes-agent:v2026.8.3"

# Deployment payload lives in the IMMUTABLE image tree (NOT under
# HERMES_HOME=/opt/data, which is the writable volume). The cont-init seed hook
# copies from here onto the volume at boot.
COPY config/  /opt/hermes-internal/config/
COPY skills/  /opt/hermes-internal/skills/
COPY scripts/ /opt/hermes-internal/scripts/

# Boot-time seed hook. Runs as root during s6 cont-init, in lexicographic order
# AFTER the base image's own init (which seeds defaults + chowns the volume), so
# our files take precedence. See the script header for the overwrite policy.
COPY --chmod=0755 docker/cont-init.d/03-hermes-internal-seed /etc/cont-init.d/03-hermes-internal-seed

# Ensure our scripts are executable even if the build context lost the mode bit.
RUN chmod 0755 /opt/hermes-internal/scripts/*.sh \
    /opt/hermes-internal/skills/endpoint-healthcheck/scripts/run_healthcheck.py

# The base image already sets HERMES_HOME=/opt/data and the s6 ENTRYPOINT
# (entrypoint-dispatch.sh -> /init). Our CMD is a verifying wrapper: it seeds
# the config-as-code on EVERY start path (covering non-PID-1 platforms where the
# cont-init hook is skipped) and hard-fails if the applied config does not match
# this image — so the agent never starts silently on the default config.
# It then execs `hermes gateway run` (the resident gateway + built-in scheduler).
# To run something else, override the args, e.g.:
#   docker run <image> /opt/hermes-internal/scripts/entrypoint.sh cron list
CMD ["/opt/hermes-internal/scripts/entrypoint.sh", "gateway", "run"]
