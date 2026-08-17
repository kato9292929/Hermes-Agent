#!/usr/bin/env bash
# Budget-enforcing wrapper around the Hermes mpp-agent skill (mppx client).
#
# It: (1) obtains the 402 challenge, (2) parses it + chooses the client +
# checks the per-request ($0.10) and task-total ($0.50) caps via challenge.py,
# (3) on ALLOW performs the actual paid call with `mppx` (environment B), and
# (4) appends a full record. It never reads wallet keys (SKILL.md:115) and never
# hides a failure: an unexpected response makes it exit non-zero.
#
# Environment A: run with --challenge-file <fixture> to exercise probe→parse→
# budget→record with NO network. Environment B: omit it to probe the live URL.
#
# UNVERIFIED (environment B, needs keys+network): the live `curl` probe, the
# real `www-authenticate` wire format, the `mppx` invocation, and its receipt
# output are not exercised in environment A. Those branches are marked below.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
VAR="$ROOT/var"; mkdir -p "$VAR"
SPEND_LEDGER="$VAR/spend-ledger.jsonl"      # append-only cumulative spend
RUN_RECORDS="$VAR/run-records.jsonl"        # append-only full run records

URL=""; METHOD="GET"; DATA=""; CHALLENGE_FILE=""; DRY_RUN=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --method) METHOD="$2"; shift 2;;
        --data) DATA="$2"; shift 2;;
        --challenge-file) CHALLENGE_FILE="$2"; DRY_RUN=1; shift 2;;
        --dry-run) DRY_RUN=1; shift;;
        http://*|https://*) URL="$1"; shift;;
        *) echo "unknown arg: $1" >&2; exit 64;;
    esac
done
[ -n "$URL" ] || { echo "usage: mpp-pay.sh <url> [--method M --data JSON] [--challenge-file F]" >&2; exit 64; }

now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# --- 1. Obtain the 402 challenge -------------------------------------------
if [ -n "$CHALLENGE_FILE" ]; then
    RESP_HEADERS="$(cat "$CHALLENGE_FILE")"
else
    # UNVERIFIED (env B): live probe. `curl -i` per SKILL.md:67.
    RESP_HEADERS="$(curl -sS -i --max-time 30 "$URL")"
fi

# Extract the www-authenticate header value (case-insensitive), fail loud if absent.
# `|| true` so a no-match (not an MPP 402) reaches the explicit FATAL check
# below instead of aborting under `set -o pipefail`.
WWW_AUTH="$({ printf '%s\n' "$RESP_HEADERS" | grep -iE '^www-authenticate:' || true; } \
    | head -1 | sed -E 's/^[Ww][Ww][Ww]-[Aa]uthenticate:[[:space:]]*//' | tr -d '\r')"
if [ -z "$WWW_AUTH" ]; then
    echo "FATAL: no www-authenticate header in response — not an MPP 402 (do not proceed)." >&2
    printf '%s\n' "$RESP_HEADERS" | head -20 >&2
    exit 75
fi

# --- 2. Parse + choose client + budget check (pure) ------------------------
SPENT_USD="$(python3 - "$SPEND_LEDGER" <<'PY'
import json, os, sys
path = sys.argv[1]
total = 0.0
if os.path.exists(path):
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("status") == "paid":
            total += float(r.get("amount_usd", 0) or 0)
print(f"{total:.6f}")
PY
)"

DECISION_JSON="$(cd "$HERE" && python3 challenge.py "$WWW_AUTH" "$SPENT_USD")"
CLIENT="$(printf '%s' "$DECISION_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin)["client"])')"
BUDGET_DECISION="$(printf '%s' "$DECISION_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin)["budget"]["decision"])')"
AMOUNT_USD="$(printf '%s' "$DECISION_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin)["budget"].get("amount_usd",0))')"
TARGET="$(printf '%s' "$DECISION_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin)["target"])')"

record() {  # status, tx, response_body, http_status, duration_ms
    python3 - "$RUN_RECORDS" "$SPEND_LEDGER" "$URL" "$CLIENT" "$WWW_AUTH" \
        "$1" "$AMOUNT_USD" "${2:-}" "${5:-}" "$(now_iso)" "$DRY_RUN" <<'PY'
import json, sys
records, ledger, url, client, wwwauth, status, amount, tx, http_status, ts, dry = sys.argv[1:12]
body = sys.stdin.read()
rec = {
    "ts": ts, "url": url, "client": client, "dry_run": bool(int(dry)),
    "www_authenticate": wwwauth, "budget_decision": status,
    "amount_usd": float(amount or 0), "payment_ref": tx or None,
    "http_status": http_status or None, "response_body": body if body else None,
}
with open(records, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
# Only a genuinely-paid call adds to cumulative spend.
if status == "paid":
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts, "url": url, "amount_usd": float(amount or 0),
                            "status": "paid", "payment_ref": tx or None}, ensure_ascii=False) + "\n")
PY
}

echo "challenge: $WWW_AUTH"
echo "client:    $CLIENT   target: $TARGET"
echo "spent so far: \$$SPENT_USD   this: \$$AMOUNT_USD   budget: $BUDGET_DECISION"

# --- 3. Enforce budget -----------------------------------------------------
if [ "$BUDGET_DECISION" = "deny" ]; then
    echo "BUDGET STOP: payment refused; recording and stopping (raise the cap is a human decision)." >&2
    printf '%s' "" | record "budget_denied"
    exit 3
fi

# --- 4. Pay (environment B) ------------------------------------------------
if [ "$CLIENT" = "link-cli" ]; then
    # A stripe-method challenge must go through the stripe-link-cli skill, not
    # mppx. We do not silently pay it here (that would be a hidden fallback).
    echo "STOP: challenge requires Stripe Link (method=stripe). Use the stripe-link-cli skill." >&2
    printf '%s' "" | record "needs_link_cli"
    exit 4
fi

if [ "$DRY_RUN" = "1" ]; then
    echo "[dry-run] would run: mppx $URL${METHOD:+ --method $METHOD}${DATA:+ --data '...'}"
    printf '%s' "" | record "dry_run_allow"
    exit 0
fi

# UNVERIFIED (env B): the real paid call. mppx handles the 402 dance and prints
# the merchant response (SKILL.md:80-89). Any non-zero exit is surfaced, not
# swallowed. `set -e` + explicit check keep a failed payment from being recorded
# as success.
START_MS="$(python3 -c 'import time;print(int(time.time()*1000))')"
set +e
if [ "$METHOD" = "GET" ]; then
    MPPX_OUT="$(mppx "$URL" -v 2>&1)"; RC=$?
else
    MPPX_OUT="$(mppx "$URL" --method "$METHOD" --data "$DATA" -v 2>&1)"; RC=$?
fi
set -e
END_MS="$(python3 -c 'import time;print(int(time.time()*1000))')"
DUR=$((END_MS - START_MS))

if [ "$RC" -ne 0 ]; then
    echo "FATAL: mppx exited $RC (payment/response failed). Recording failure." >&2
    printf '%s' "$MPPX_OUT" | record "mppx_failed"
    exit 76
fi

# mppx printed the merchant response. The receipt/tx id parsing from `-v` output
# is UNVERIFIED (env B) — we store the full output verbatim rather than guess a
# field name.
printf '%s' "$MPPX_OUT" | record "paid" "SEE_MPPX_OUTPUT" "" "" "$DUR"
echo "PAID (\$$AMOUNT_USD). duration ${DUR}ms. Full mppx output recorded."
