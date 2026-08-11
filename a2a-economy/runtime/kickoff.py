"""Send a goal to the orchestrator and print the returned cycle record.

This is the external trigger — it mirrors how, in env B, one would send the
orchestrator agent a goal message over A2A. It does not do any of the cycle work
itself; the orchestrator (a separate process) drives all 8 stages.
"""

from __future__ import annotations

import argparse
import json
import sys

from runtime import economy_config as C
from runtime.transport import extract_data, get_transport, new_context_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kick off one economy cycle.")
    parser.add_argument("--goal-file", required=True,
                        help="JSON: {cycle_id, goal, orders, select_index}")
    args = parser.parse_args(argv)

    with open(args.goal_file, encoding="utf-8") as f:
        goal = json.load(f)

    transport = get_transport()
    reply = transport.call(C.url("orchestrator"), goal, new_context_id(),
                           token=C.TOKENS["orchestrator"])
    if "error" in reply:
        print(f"orchestrator error: {reply['error']}", file=sys.stderr)
        return 1
    record = extract_data(reply)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
