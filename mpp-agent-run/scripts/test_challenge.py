#!/usr/bin/env python3
"""Environment-A tests for challenge.py — parsing, client choice, budget caps.
Hermetic (no network). Run: python3 scripts/test_challenge.py
"""
import sys

from challenge import (PER_REQUEST_CAP_USD, TOTAL_CAP_USD, check_budget,
                       choose_client, parse_challenge)

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# 1. Single Tempo challenge (SKILL.md:74 form)
chs = parse_challenge("tempo amount=0.1 currency=USDC")
check("single tempo parsed", len(chs) == 1 and chs[0].scheme == "tempo")
check("amount parsed", chs[0].amount == 0.1 and chs[0].currency == "USDC")
check("client=mppx for tempo", choose_client(chs)["client"] == "mppx")

# 2. Multiple methods, one is stripe (SKILL.md:113) -> link-cli
chs = parse_challenge('tempo amount=0.05 currency=USDC, stripe method="stripe" amount=0.05 currency=USD')
check("two challenges split", len(chs) == 2)
choice = choose_client(chs)
check("client=link-cli when method=stripe present", choice["client"] == "link-cli")

# 3. Zero-amount proof credential is allowed, not broken (SKILL.md:114)
b = check_budget(0.0, None, spent_usd=0.0)
check("zero-amount allowed", b["decision"] == "allow")

# 4. Per-request cap: $0.20 > $0.10 denied
b = check_budget(0.20, "USDC", spent_usd=0.0)
check("over per-request cap denied", b["decision"] == "deny")

# 5. Within per-request but exceeds total: spent 0.48 + 0.05 > 0.50
b = check_budget(0.05, "USDC", spent_usd=0.48)
check("over total cap denied", b["decision"] == "deny")

# 6. Within both caps allowed
b = check_budget(0.005, "USDC", spent_usd=0.10)
check("within caps allowed", b["decision"] == "allow" and abs(b["amount_usd"] - 0.005) < 1e-9)

# 7. Unknown currency FAILS LOUDLY (no invented FX)
try:
    check_budget(0.05, "JPY", spent_usd=0.0)
    check("unknown currency raises", False)
except ValueError:
    check("unknown currency raises", True)

# 8. Missing amount FAILS LOUDLY (do not assume)
try:
    check_budget(None, "USDC", spent_usd=0.0)
    check("missing amount raises", False)
except ValueError:
    check("missing amount raises", True)

# 9. Garbage header FAILS LOUDLY
try:
    parse_challenge("===not a challenge==")
    check("garbage header raises", False)
except ValueError:
    check("garbage header raises", True)

# 10. Caps are the work-order values
check("caps are $0.10 / $0.50", PER_REQUEST_CAP_USD == 0.10 and TOTAL_CAP_USD == 0.50)

print()
if fails:
    print(f"{len(fails)} FAILED: {fails}")
    sys.exit(1)
print("ALL TESTS PASSED")
