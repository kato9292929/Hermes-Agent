#!/usr/bin/env bash
# Bring up the 3 actors and run ALL cases (every decline reason + every verdict)
# into a fresh ledger. Order is fixed so docs/sample-cycle.md is reproducible.
set -euo pipefail

cd "$(dirname "$0")/.."          # a2a-economy/
ROOT="$(pwd)"
export PYTHONPATH="$ROOT"
export A2A_ECONOMY_TRANSPORT="${A2A_ECONOMY_TRANSPORT:-http-local}"
export A2A_ECONOMY_PAYMENT="${A2A_ECONOMY_PAYMENT:-mock}"
export NO_PROXY="127.0.0.1,localhost"; export no_proxy="127.0.0.1,localhost"

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

# Fixed order: PASS, then the 4 decline reasons, then FAIL, then INVALID.
CASES=(
    goal-accept.json
    goal-reject.json
    goal-malformed.json
    goal-unsupported.json
    goal-overbudget.json
    goal-fail.json
    goal-invalid.json
)
for c in "${CASES[@]}"; do
    echo "--- $c ---"
    python3 -m runtime.kickoff --goal-file "goals/$c" | python3 -c \
        "import json,sys; d=json.load(sys.stdin); print('  ->', d['cycle_id'], '| executed=', d['executed'], '| verdict=', d['verdict']['verdict'])"
done

echo "=== all cases done; ledger at var/ledger.jsonl ==="
