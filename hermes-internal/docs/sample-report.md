# Sample daily report output

> **This is output against a LOCAL DUMMY SERVER, not production endpoints.**
> The URLs below (`https://example.internal/...`, `https://legacy.example.internal/...`)
> are placeholders. It was produced by running
> `skills/endpoint-healthcheck/scripts/run_healthcheck.py` against a throwaway
> `http.server` on `127.0.0.1`, then rewriting the local URLs to dummy ones.
> Timings and error text are real; hostnames are not.

It exercises all five paths the health check can produce:

| Path | Represented by | Result |
|---|---|---|
| 200 OK + required fields present | `billing-api` | OK |
| x402 gate returns 402 as expected | `x402-paywall` | OK (402 is healthy here) |
| Required JSON field missing | `profile-api` (expects `data.email`) | ANOMALY |
| Host unreachable | `legacy-worker` (connection refused) | ANOMALY |
| No targets configured | empty `targets.yaml` | exit 3 (shown at the end) |

The header tells you the verdict in one glance: `❌ 2 ANOMALY(IES)` vs `✅ ALL OK`,
with OK/failed counts, a per-target table, and an `## Anomalies` section that
names each failing target and exactly what was wrong.

---

## 1. Markdown report (stdout / `--md-out` / `--deliver`)

This is what lands in the daily notification.

```markdown
# Endpoint health report — ❌ 2 ANOMALY(IES)

- Generated (UTC): `2026-08-08T08:55:15Z`
- Targets checked: **4**  |  OK: **2**  |  Failed: **2**

| Target | Status | Expected | Time (ms) | Result |
|---|---|---|---|---|
| billing-api | 200 | 200 | 5.2 | OK |
| x402-paywall | 402 | 402 | 2.4 | OK |
| profile-api | 200 | 200 | 2.6 | ANOMALY |
| legacy-worker | — | 200 | 6.5 | ANOMALY |

## Anomalies
- **profile-api** (`https://example.internal/profile/health`):
  - missing required JSON field: data.email
- **legacy-worker** (`https://legacy.example.internal/health`):
  - unreachable: URLError: <urlopen error [Errno 111] Connection refused>
```

Rendered, the header line and the `## Anomalies` block are what a human reads in
~5 seconds; the table is the detail. An all-healthy run collapses to
`# Endpoint health report — ✅ ALL OK` with an empty anomalies section.

---

## 2. Structured JSON (`--json-out`)

Written to `$HERMES_HOME/cron/output/healthcheck.json` for machine consumption
(dashboards, diffing day-over-day, feeding a webhook receiver).

```json
{
  "generated_at_utc": "2026-08-08T08:55:15Z",
  "summary": {
    "total": 4,
    "ok": 2,
    "failed": 2
  },
  "results": [
    {
      "name": "billing-api",
      "url": "https://example.internal/billing/health",
      "method": "GET",
      "expect_status": 200,
      "status_code": 200,
      "response_time_ms": 5.2,
      "ok": true,
      "anomalies": [],
      "checked_fields": [
        { "field": "status", "present": true },
        { "field": "data.version", "present": true }
      ]
    },
    {
      "name": "x402-paywall",
      "url": "https://example.internal/pay/resource",
      "method": "GET",
      "expect_status": 402,
      "status_code": 402,
      "response_time_ms": 2.4,
      "ok": true,
      "anomalies": [],
      "checked_fields": []
    },
    {
      "name": "profile-api",
      "url": "https://example.internal/profile/health",
      "method": "GET",
      "expect_status": 200,
      "status_code": 200,
      "response_time_ms": 2.6,
      "ok": false,
      "anomalies": [
        "missing required JSON field: data.email"
      ],
      "checked_fields": [
        { "field": "status", "present": true },
        { "field": "data.email", "present": false }
      ]
    },
    {
      "name": "legacy-worker",
      "url": "https://legacy.example.internal/health",
      "method": "GET",
      "expect_status": 200,
      "status_code": null,
      "response_time_ms": 6.5,
      "ok": false,
      "anomalies": [
        "unreachable: URLError: <urlopen error [Errno 111] Connection refused>"
      ],
      "checked_fields": []
    }
  ]
}
```

Process exit code for this run was **2** (at least one anomaly), so a
scheduler/CI step that checks the exit code also sees the failure — not just the
text.

---

## 3. No targets configured (exit 3)

When `targets.yaml` has an empty list, the runner does not pretend success. It
writes nothing to stdout and prints to stderr, exiting **3**:

```
No targets configured in .../targets.yaml. Add entries (see targets.example.yaml).
```

The cron wrapper `scripts/healthcheck.sh` turns this into a visible stdout line
so the empty state shows up in the daily delivery rather than arriving silent:

```markdown
# Endpoint health report — NO TARGETS CONFIGURED

targets.yaml is empty. Add endpoints (see targets.example.yaml).
```

---

## How this was produced

```bash
# a local dummy server served /billing/health and /profile/health (200 JSON),
# /pay/resource (402); legacy-worker pointed at a refused port.
python3 skills/endpoint-healthcheck/scripts/run_healthcheck.py \
  --targets <local-targets.yaml> \
  --json-out report.json --md-out report.md
# then local 127.0.0.1 URLs were rewritten to https://example.internal/... etc.
```
