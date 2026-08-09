"""Payment — THE SINGLE SWAP POINT for mock (env A) vs real x402 (env B).

Env A: `MockPayment` returns a deterministic reference; NO funds move.
Env B: `X402Payment` is where AA's real payment is wired in. AA routes every paid
call through `fetchWithPayment` (src/x402.ts:80, backed by initX402Fetch at :47),
which supports the EVM "exact" scheme (Base) and the SVM/Solana "exact" scheme
via `registerExactSvmScheme` (src/x402.ts:71). That is the single place to bridge.
See docs/UNVERIFIED.md for the env-B swap.

Selection via env var `A2A_ECONOMY_PAYMENT` (`mock` default, or `x402`).

Label discipline: this module produces only a ledger reference. Payment COUNT
and TOTAL AMOUNT are never success metrics (see docs/evaluation-criteria.md).
"""

from __future__ import annotations

import hashlib
import os
from typing import Any


class MockPayment:
    name = "mock"

    def pay(self, order: dict[str, Any]) -> dict[str, Any]:
        # Deterministic reference (no randomness) so a cycle is reproducible.
        amount = int(order.get("estimated_cost_micro_usd", 0) or 0)
        seed = f"{order.get('name')}|{order.get('url')}|{amount}"
        ref = "mock-pay-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return {
            "paid": True,
            "scheme": "mock",
            "reference": ref,
            "amount_micro_usd": amount,
            "note": "mock payment; no funds moved",
        }


class X402Payment:
    name = "x402"

    def pay(self, order: dict[str, Any]) -> dict[str, Any]:
        # Environment B only. Replace this body with a bridge to AA's
        # fetchWithPayment (src/x402.ts:80). Fail loudly if selected in env A.
        raise NotImplementedError(
            "real x402 payment runs in environment B; wire AA fetchWithPayment "
            "(src/x402.ts:80) here — see docs/UNVERIFIED.md"
        )


def get_payment() -> Any:
    choice = os.getenv("A2A_ECONOMY_PAYMENT", "mock")
    if choice == "mock":
        return MockPayment()
    if choice == "x402":
        return X402Payment()
    raise ValueError(f"unknown A2A_ECONOMY_PAYMENT={choice!r} (expected 'mock' or 'x402')")
