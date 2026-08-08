#!/usr/bin/env python3
"""
Endpoint health check runner for the `endpoint-healthcheck` Hermes skill.

Reads a list of targets from a YAML file, probes each one over HTTP, and emits
BOTH a structured JSON result and a human-readable markdown report.

Design rules (from the work order — do NOT relax these):
  * Targets are NEVER hardcoded here. They come from `targets.yaml`.
  * An x402 payment-gated endpoint returning 402 is NOT an error when the target
    declares `expect_status: 402`. Payment execution is out of scope for this skill.
  * Exceptions are NOT swallowed into a fake "success".
      - A per-target network failure / unexpected status is recorded in the
        report as an ANOMALY (this is required reporting behavior, not swallowing)
        and forces a non-zero exit code.
      - A program-level misconfiguration (missing/unreadable targets file, bad
        YAML, unknown target keys) crashes loudly with a traceback.

Exit codes:
  0  all targets matched their expectations
  2  at least one target failed (unreachable / unexpected status / missing field)
  3  no targets configured (targets.yaml present but empty)

This script depends only on the standard library plus PyYAML (which ships with
the Hermes runtime). It deliberately does not fall back to a hand-rolled YAML
parser: if PyYAML is missing, that is a broken environment and we fail loudly.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml  # hard dependency — do not wrap in try/except

# Keys a target entry is allowed to declare. Anything else is a config error
# and must fail loudly rather than be silently ignored.
ALLOWED_TARGET_KEYS = {
    "name",
    "url",
    "method",
    "headers",
    "body",
    "timeout_seconds",
    "expect_status",
    "expect_json_fields",
}


def _load_targets(targets_path: Path) -> list[dict[str, Any]]:
    """Load and validate the targets file. Raises loudly on any problem."""
    if not targets_path.exists():
        raise FileNotFoundError(
            f"targets file not found: {targets_path} — configure it before running "
            f"(see targets.example.yaml)"
        )

    raw = yaml.safe_load(targets_path.read_text(encoding="utf-8"))
    if raw is None:
        return []
    if not isinstance(raw, dict) or "targets" not in raw:
        raise ValueError(
            f"{targets_path}: expected a mapping with a top-level 'targets:' list"
        )

    targets = raw["targets"]
    if targets is None:
        return []
    if not isinstance(targets, list):
        raise ValueError(f"{targets_path}: 'targets' must be a list")

    for i, t in enumerate(targets):
        if not isinstance(t, dict):
            raise ValueError(f"{targets_path}: targets[{i}] must be a mapping")
        if "url" not in t:
            raise ValueError(f"{targets_path}: targets[{i}] is missing required key 'url'")
        unknown = set(t) - ALLOWED_TARGET_KEYS
        if unknown:
            raise ValueError(
                f"{targets_path}: targets[{i}] ({t.get('name', t['url'])}) has unknown "
                f"key(s): {sorted(unknown)}. Allowed: {sorted(ALLOWED_TARGET_KEYS)}"
            )
    return targets


def _get_nested(obj: Any, dotted: str) -> tuple[bool, Any]:
    """Resolve a dotted path (e.g. 'data.status') in a decoded JSON body.

    Returns (found, value). Does not raise on a missing field — a missing
    required field is a reportable anomaly, not a program error.
    """
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return True, cur


def _probe(target: dict[str, Any], default_timeout: float) -> dict[str, Any]:
    """Probe a single target. Network-level failures are captured into the
    result dict as anomalies (required reporting), never swallowed as success."""
    name = target.get("name") or target["url"]
    url = target["url"]
    method = str(target.get("method", "GET")).upper()
    headers = dict(target.get("headers") or {})
    body = target.get("body")
    timeout = float(target.get("timeout_seconds", default_timeout))
    expect_status = int(target.get("expect_status", 200))
    expect_json_fields = list(target.get("expect_json_fields") or [])

    result: dict[str, Any] = {
        "name": name,
        "url": url,
        "method": method,
        "expect_status": expect_status,
        "status_code": None,
        "response_time_ms": None,
        "ok": False,
        "anomalies": [],
        "checked_fields": [],
    }

    data = body.encode("utf-8") if isinstance(body, str) else body
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    ctx = ssl.create_default_context()

    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status = resp.getcode()
            payload = resp.read()
    except urllib.error.HTTPError as exc:
        # An HTTP error status still carries a real response — record it and
        # its body so a 402/500/etc. can be evaluated against expect_status.
        status = exc.code
        payload = exc.read() if hasattr(exc, "read") else b""
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError) as exc:
        # Genuinely unreachable: DNS failure, refused, timeout, TLS failure.
        result["response_time_ms"] = round((time.monotonic() - start) * 1000, 1)
        result["anomalies"].append(f"unreachable: {type(exc).__name__}: {exc}")
        return result

    elapsed_ms = round((time.monotonic() - start) * 1000, 1)
    result["status_code"] = status
    result["response_time_ms"] = elapsed_ms

    if status != expect_status:
        result["anomalies"].append(
            f"unexpected status: got {status}, expected {expect_status}"
        )

    if expect_json_fields:
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            result["anomalies"].append(
                f"expected JSON body but could not decode it: {type(exc).__name__}: {exc}"
            )
        else:
            for field in expect_json_fields:
                found, _ = _get_nested(decoded, field)
                result["checked_fields"].append({"field": field, "present": found})
                if not found:
                    result["anomalies"].append(f"missing required JSON field: {field}")

    result["ok"] = not result["anomalies"]
    return result


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    s = report["summary"]
    header = "✅ ALL OK" if s["failed"] == 0 else f"❌ {s['failed']} ANOMALY(IES)"
    lines.append(f"# Endpoint health report — {header}")
    lines.append("")
    lines.append(f"- Generated (UTC): `{report['generated_at_utc']}`")
    lines.append(f"- Targets checked: **{s['total']}**  |  OK: **{s['ok']}**  |  Failed: **{s['failed']}**")
    lines.append("")
    lines.append("| Target | Status | Expected | Time (ms) | Result |")
    lines.append("|---|---|---|---|---|")
    for r in report["results"]:
        code = r["status_code"] if r["status_code"] is not None else "—"
        verdict = "OK" if r["ok"] else "ANOMALY"
        lines.append(
            f"| {r['name']} | {code} | {r['expect_status']} | "
            f"{r['response_time_ms'] if r['response_time_ms'] is not None else '—'} | {verdict} |"
        )
    anomalies = [r for r in report["results"] if r["anomalies"]]
    if anomalies:
        lines.append("")
        lines.append("## Anomalies")
        for r in anomalies:
            lines.append(f"- **{r['name']}** (`{r['url']}`):")
            for a in r["anomalies"]:
                lines.append(f"  - {a}")
    return "\n".join(lines) + "\n"


def _utc_now_iso() -> str:
    # Import here so the module has no import-time clock dependency.
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run endpoint health checks.")
    default_targets = Path(__file__).resolve().parent.parent / "targets.yaml"
    parser.add_argument(
        "--targets",
        type=Path,
        default=default_targets,
        help=f"Path to targets YAML (default: {default_targets})",
    )
    parser.add_argument(
        "--default-timeout",
        type=float,
        default=15.0,
        help="Default per-target timeout in seconds (default: 15)",
    )
    parser.add_argument("--json-out", type=Path, default=None, help="Write JSON report to this path")
    parser.add_argument("--md-out", type=Path, default=None, help="Write markdown report to this path")
    args = parser.parse_args(argv)

    targets = _load_targets(args.targets)

    if not targets:
        # Explicit, visible outcome — not a swallowed success.
        msg = f"No targets configured in {args.targets}. Add entries (see targets.example.yaml)."
        print(msg, file=sys.stderr)
        return 3

    results = [_probe(t, args.default_timeout) for t in targets]
    ok_count = sum(1 for r in results if r["ok"])
    report = {
        "generated_at_utc": _utc_now_iso(),
        "summary": {"total": len(results), "ok": ok_count, "failed": len(results) - ok_count},
        "results": results,
    }

    json_text = json.dumps(report, indent=2, ensure_ascii=False)
    md_text = _render_markdown(report)

    if args.json_out:
        args.json_out.write_text(json_text + "\n", encoding="utf-8")
    if args.md_out:
        args.md_out.write_text(md_text, encoding="utf-8")

    # Always print the markdown to stdout so a cron/oneshot run surfaces it.
    print(md_text)
    if not args.json_out:
        # Emit JSON on stderr when not written to a file, so structured data is
        # never lost but does not corrupt the markdown on stdout.
        print(json_text, file=sys.stderr)

    return 0 if report["summary"]["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
