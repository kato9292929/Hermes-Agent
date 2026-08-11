"""Shared configuration for the 3-actor economy (environment A defaults).

Ports + HERMES_HOME dirs are the units of isolation (docs/a2a-facts.md §5:
distinct A2A_PORT + distinct HERMES_HOME per instance). The tokens here are
LOCAL-ONLY dev tokens for the localhost HTTP stand-in; environment B uses real
A2A bearer tokens via A2A_PEER_TOKENS and never these defaults.
"""

from __future__ import annotations

import os

# a2a-economy/ root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAR = os.path.join(ROOT, "var")

ROLES = ("orchestrator", "worker", "evaluator")

PORTS = {
    "orchestrator": int(os.getenv("ORCH_PORT", "9901")),
    "worker": int(os.getenv("WORKER_PORT", "9902")),
    "evaluator": int(os.getenv("EVAL_PORT", "9903")),
}

# Each actor's own HERMES_HOME (isolation unit). Mirrors real multi-instance A2A.
HOMES = {role: os.path.join(VAR, "homes", role) for role in ROLES}

# Local-only dev bearer tokens (NOT secrets; localhost stand-in only).
TOKENS = {
    "orchestrator": os.getenv("ORCH_TOKEN", "dev-orchestrator"),
    "worker": os.getenv("WORKER_TOKEN", "dev-worker"),
    "evaluator": os.getenv("EVAL_TOKEN", "dev-evaluator"),
}

LEDGER = os.path.join(VAR, "ledger.jsonl")
CRITERIA_REF = "a2a-economy/docs/evaluation-criteria.md"

# Budget cap used by the acceptance policy. A control value, NOT a metric.
BUDGET_CAP_MICRO_USD = int(os.getenv("BUDGET_CAP_MICRO_USD", "1000000"))  # $1.00


def url(role: str) -> str:
    return f"http://127.0.0.1:{PORTS[role]}/"
