#!/usr/bin/env bash
# Bring up the 3 actors as SEPARATE processes, run both cycles (execute path and
# reject/non-execution path), then shut them down. Environment-A end-to-end.
#
# Each actor gets its own HERMES_HOME and its own port (the A2A isolation unit).
# The ledger and per-actor audit logs are written under a2a-economy/var/.
set -euo pipefail

cd "$(dirname "$0")/.."          # a2a-economy/
ROOT="$(pwd)"
export PYTHONPATH="$ROOT"
export A2A_ECONOMY_TRANSPORT="${A2A_ECONOMY_TRANSPORT:-http-local}"
export A2A_ECONOMY_PAYMENT="${A2A_ECONOMY_PAYMENT:-mock}"
export NO_PROXY="127.0.0.1,localhost"; export no_proxy="127.0.0.1,localhost"

# Fresh state so the sample is reproducible.
rm -f var/ledger.jsonl
rm -rf var/homes
mkdir -p var/homes

PIDS=()
cleanup() { for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT

for role in worker evaluator orchestrator; do
    python3 -m runtime.actor --role "$role" &
    PIDS+=("$!")
done

# Wait for all three health endpoints.
python3 - <<'PY'
import time, urllib.request, sys
from runtime import economy_config as C
for role in C.ROLES:
    for _ in range(100):
        try:
            with urllib.request.urlopen(C.url(role) + "health", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.05)
    else:
        print(f"actor {role} did not come up", file=sys.stderr); sys.exit(1)
print("all 3 actors up")
PY

echo "=== cycle 1: execute path ==="
python3 -m runtime.kickoff --goal-file goals/goal-accept.json

echo "=== cycle 2: reject / non-execution path ==="
python3 -m runtime.kickoff --goal-file goals/goal-reject.json

echo "=== ledger (var/ledger.jsonl) ==="
cat var/ledger.jsonl
