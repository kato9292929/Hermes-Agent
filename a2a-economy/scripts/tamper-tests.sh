#!/usr/bin/env bash
# Prove the re-verifier catches tampering. Three tampered COPIES are made from
# var/ledger.jsonl (the original is never modified); the verifier must reject
# each with a non-zero exit code. Work order M3.
set -uo pipefail

cd "$(dirname "$0")/.."          # a2a-economy/
ROOT="$(pwd)"; export PYTHONPATH="$ROOT"
SRC="var/ledger.jsonl"
TDIR="var/tamper"
rm -rf "$TDIR"; mkdir -p "$TDIR"

if [ ! -f "$SRC" ]; then echo "run scripts/run-all-cases.sh first" >&2; exit 2; fi

# Build the three tampered copies with a small pure-JSON transform each.
python3 - "$SRC" "$TDIR" <<'PY'
import json, sys
src, tdir = sys.argv[1], sys.argv[2]
rows = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]

def dump(rows, name):
    with open(f"{tdir}/{name}", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def clone(rows):
    return [json.loads(json.dumps(r)) for r in rows]

# 1) verdict tamper: flip a declined cycle's verdict to PASS
a = clone(rows)
for r in a:
    if r.get("type") == "cycle" and r["cycle_id"] == "cycle-reject-001":
        r["verdict"]["verdict"] = "PASS"
dump(a, "tamper1-verdict.jsonl")

# 2) reason tamper: change the decline reason (keep verdict NON_EXECUTION_VALID)
b = clone(rows)
for r in b:
    if r.get("type") == "cycle" and r["cycle_id"] == "cycle-reject-001":
        r["decision"]["reason"] = "over_budget"
dump(b, "tamper2-reason.jsonl")

# 3) input tamper: edit the work order's expect_status to match the actual result
c = clone(rows)
for r in c:
    if r.get("type") == "cycle" and r["cycle_id"] == "cycle-fail-001":
        r["order"]["expect_status"] = r["order"]["response"]["status_code"]  # 200 -> 500
dump(c, "tamper3-input.jsonl")
print("wrote 3 tampered copies")
PY

rc_all=0
for t in tamper1-verdict tamper2-reason tamper3-input; do
    echo "================ $t ================"
    PYTHONPATH="$ROOT" python3 -m runtime.verify_ledger "$TDIR/$t.jsonl"
    rc=$?
    echo ">>> exit code: $rc  (expected non-zero)"
    if [ "$rc" -eq 0 ]; then echo "!!! NOT DETECTED"; rc_all=1; fi
    echo
done

echo "================ original (control) ================"
PYTHONPATH="$ROOT" python3 -m runtime.verify_ledger "$SRC" >/dev/null 2>&1
echo ">>> original exit code: $?  (expected 0)"

exit "$rc_all"
