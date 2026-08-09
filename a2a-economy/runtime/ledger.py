"""Append-only ledger + per-actor A2A audit log.

The cycle ledger is OUR record of every stage (input, output, which actor
produced it, timestamp). We keep it ourselves rather than relying on A2A's audit,
because A2A does not persist every decline (docs/a2a-facts.md §4). Non-execution
MUST be recorded — a cycle that does not execute still writes stages 7 and 8.

The per-actor audit mirrors the real A2A audit line
($HERMES_HOME/a2a_audit.jsonl, docs/a2a-facts.md §4) so the env-B behavior is
visible in env A too.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any


def _now_iso() -> str:
    # Real wall-clock is fine here (plain Python, not a workflow script).
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def append_jsonl(path: str, record: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


class Ledger:
    """Append-only cycle ledger."""

    def __init__(self, path: str) -> None:
        self.path = path

    def stage(self, cycle_id: str, stage_no: int, stage: str, actor: str,
              inputs: Any, output: Any) -> dict[str, Any]:
        rec = {
            "type": "stage",
            "cycle_id": cycle_id,
            "stage_no": stage_no,
            "stage": stage,
            "actor": actor,
            "ts": _now_iso(),
            "input": inputs,
            "output": output,
        }
        append_jsonl(self.path, rec)
        return rec

    def cycle(self, record: dict[str, Any]) -> None:
        rec = dict(record)
        rec["type"] = "cycle"
        rec.setdefault("ts", _now_iso())
        append_jsonl(self.path, rec)


def audit(hermes_home: str, direction: str, peer: str, task_id: str, summary: str) -> None:
    """Mirror the real A2A audit line: $HERMES_HOME/a2a_audit.jsonl."""
    path = os.path.join(hermes_home, "a2a_audit.jsonl")
    append_jsonl(path, {
        "ts": _now_iso(),
        "direction": direction,
        "peer": peer,
        "task_id": task_id,
        "summary": summary[:500],
    })
