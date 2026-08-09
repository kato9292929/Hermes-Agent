"""One actor process = one role, one port, one HERMES_HOME.

Run three of these (orchestrator / worker / evaluator) as SEPARATE OS processes.
They speak the A2A v1.0 JSON-RPC `SendMessage` envelope to each other through
runtime/transport.py (localhost HTTP in env A; real Hermes A2A in env B).

  python3 -m runtime.actor --role worker
  python3 -m runtime.actor --role evaluator
  python3 -m runtime.actor --role orchestrator

The orchestrator, on receiving a "goal" message, drives the 8-stage cycle by
calling the worker then the evaluator, writing every stage to the ledger.

Auth mirrors A2A: caller identity is derived from the bearer token (never the
body); an unknown token is 401. No exception is swallowed into a fake success —
a handler error becomes a JSON-RPC error, not a COMPLETED task.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from runtime import economy_config as C
from runtime import evaluator as evaluator_mod
from runtime import ledger as ledger_mod
from runtime import worker_policy
from runtime.payment import get_payment
from runtime.transport import (
    build_reply,
    extract_data,
    get_transport,
    new_context_id,
    reply_state,
    STATE_COMPLETED,
    STATE_REJECTED,
)
from worker_task import endpoint_verify

# token -> caller name (mirrors A2A A2A_PEER_TOKENS name:token mapping)
_TOKEN_TO_NAME = {tok: name for name, tok in C.TOKENS.items()}


def _identity_from_auth(header: str | None) -> str | None:
    if not header or not header.startswith("Bearer "):
        return None
    presented = header[len("Bearer "):].strip()
    for tok, name in _TOKEN_TO_NAME.items():
        if hmac.compare_digest(presented, tok):
            return name
    return None


# --------------------------- role handlers ---------------------------------

def handle_worker(data: dict[str, Any], home: str, caller: str) -> tuple[dict[str, Any], str]:
    """Stage 5: accept/decline, and (if accepted) run the verification."""
    order = data["order"]
    ledger_mod.audit(home, "inbound", caller, data.get("task_id", "-"),
                     f"work order {order.get('name')}")
    decision = worker_policy.decide(order, C.BUDGET_CAP_MICRO_USD)
    result = endpoint_verify.verify(order) if decision["accepted"] else None
    state = STATE_COMPLETED if decision["accepted"] else STATE_REJECTED
    return {"decision": decision, "result": result}, state


def handle_evaluator(data: dict[str, Any], home: str, caller: str) -> tuple[dict[str, Any], str]:
    """Stage 7: deterministic verdict by re-derivation."""
    order = data["order"]
    ledger_mod.audit(home, "inbound", caller, data.get("task_id", "-"),
                     f"evaluate {order.get('name')}")
    verdict = evaluator_mod.evaluate(order, data["decision"], data.get("result"),
                                     C.BUDGET_CAP_MICRO_USD)
    return {"verdict": verdict}, STATE_COMPLETED


def handle_orchestrator(data: dict[str, Any], home: str, caller: str) -> tuple[dict[str, Any], str]:
    """Drive the 8-stage cycle. `data` = {cycle_id, goal, orders, select_index}."""
    transport = get_transport()
    payment = get_payment()
    ledger = ledger_mod.Ledger(C.LEDGER)
    ctx = new_context_id()

    cid = data["cycle_id"]
    goal = data["goal"]
    orders = data["orders"]
    idx = int(data.get("select_index", 0))

    # 1 目的
    ledger.stage(cid, 1, "目的(goal)", "orchestrator", {"goal": goal}, {"goal": goal})
    # 2 分解
    units = [o.get("name") or o.get("url") for o in orders]
    ledger.stage(cid, 2, "分解(decompose)", "orchestrator", {"goal": goal}, {"units": units})
    # 3 候補
    ledger.stage(cid, 3, "候補(candidates)", "orchestrator", {"units": units},
                 {"candidates": units})
    # 4 選択
    order = orders[idx]
    ledger.stage(cid, 4, "選択(select)", "orchestrator", {"candidates": units},
                 {"selected": order.get("name")})

    # 5 可否 (Worker)
    wtoken = C.TOKENS["orchestrator"]  # our token when calling out
    ledger_mod.audit(home, "outbound", "worker", cid, f"send order {order.get('name')}")
    wreply = transport.call(C.url("worker"), {"order": order, "task_id": cid}, ctx,
                            token=wtoken)
    wdata = extract_data(wreply)
    decision = wdata["decision"]
    result = wdata.get("result")
    ledger.stage(cid, 5, "可否(accept/decline)", "worker",
                 {"order": order.get("name")},
                 {"decision": decision, "result": result, "a2a_state": reply_state(wreply)})

    # 6 決済 (mock; skipped if declined)
    if decision["accepted"]:
        payref = payment.pay(order)
    else:
        payref = None
    ledger.stage(cid, 6, "決済(payment)", "orchestrator",
                 {"accepted": decision["accepted"]}, {"payment": payref})

    # 7 評価 (Evaluator)
    ledger_mod.audit(home, "outbound", "evaluator", cid, f"evaluate {order.get('name')}")
    ereply = transport.call(
        C.url("evaluator"),
        {"order": order, "decision": decision, "result": result, "task_id": cid},
        ctx, token=wtoken,
    )
    verdict = extract_data(ereply)["verdict"]
    ledger.stage(cid, 7, "評価(evaluate)", "evaluator",
                 {"order": order.get("name"), "accepted": decision["accepted"]},
                 {"verdict": verdict})

    # 8 実績
    executed = bool(decision["accepted"])
    cycle_record = {
        "cycle_id": cid,
        "criteria_ref": C.CRITERIA_REF,
        "context_id": ctx,
        "goal": goal,
        "selected_order": {k: order.get(k) for k in ("name", "url", "expect_status")},
        "decision": decision,
        "executed": executed,
        "payment": payref,
        "verdict": verdict,
        "actors": {
            "orchestrator": {"identity": "orchestrator"},
            "worker": {"identity": "worker"},
            "evaluator": {"identity": "evaluator"},
        },
    }
    ledger.cycle(cycle_record)
    ledger.stage(cid, 8, "実績(record)", "orchestrator",
                 {"executed": executed}, {"verdict": verdict["verdict"], "executed": executed})
    return cycle_record, STATE_COMPLETED


_HANDLERS = {
    "worker": handle_worker,
    "evaluator": handle_evaluator,
    "orchestrator": handle_orchestrator,
}


# ------------------------------- server ------------------------------------

def make_handler(role: str, home: str):
    handler_fn = _HANDLERS[role]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _json(self, code: int, obj: dict[str, Any]) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/health"):
                self._json(200, {"status": "ok", "role": role})
            elif self.path in ("/.well-known/agent-card.json", "/.well-known/agent.json"):
                self._json(200, {
                    "name": f"economy-{role}",
                    "description": f"internal-economy {role}",
                    "version": "1.0.0",
                    "protocolVersion": "1.0",
                    "capabilities": {"streaming": False, "pushNotifications": False},
                })
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            # Identity from bearer token, never from the body (A2A rule).
            caller = _identity_from_auth(self.headers.get("Authorization"))
            if caller is None:
                self._json(401, {"jsonrpc": "2.0", "id": None,
                                 "error": {"code": 401, "message": "unauthorized"}})
                return
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(length).decode("utf-8"))
            req_id = req.get("id")
            ctx = req.get("params", {}).get("message", {}).get("contextId")
            try:
                data = extract_data(req)
                out, state = handler_fn(data, home, caller)
            except Exception as exc:  # surface as JSON-RPC error — never fake success
                self._json(200, {"jsonrpc": "2.0", "id": req_id,
                                 "error": {"code": -32000,
                                           "message": f"{type(exc).__name__}: {exc}"}})
                return
            self._json(200, build_reply(req_id, out, ctx, state=state))

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one economy actor.")
    parser.add_argument("--role", required=True, choices=C.ROLES)
    args = parser.parse_args(argv)
    role = args.role

    home = os.environ.get("HERMES_HOME") or C.HOMES[role]
    os.makedirs(home, exist_ok=True)
    port = C.PORTS[role]

    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(role, home))
    print(f"[{role}] listening on 127.0.0.1:{port}  HERMES_HOME={home}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
