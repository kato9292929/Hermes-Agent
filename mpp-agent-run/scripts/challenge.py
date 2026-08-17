#!/usr/bin/env python3
"""Parse an MPP `www-authenticate` 402 challenge, choose the mpp-agent client,
and enforce the payment budget. PURE + HERMETIC (no network) so it is fully
testable in environment A.

Grounded only in the mpp-agent SKILL.md
(optional-skills/payments/mpp-agent/SKILL.md at Hermes tag v2026.8.3):
  - challenge form `www-authenticate: tempo amount=0.1 currency=...` (SKILL.md:74)
  - `method="stripe"` -> pay via Stripe Link (link-cli); otherwise mppx picks the
    Tempo method (SKILL.md:30, :36, :112-113)
  - multiple methods may appear in one header, e.g. `tempo, stripe` (SKILL.md:113)
  - zero-amount challenges are valid, not broken (SKILL.md:114)

Anything the SKILL.md does not state is NOT invented here — unknown currencies
and unparseable challenges FAIL LOUDLY (raise), they are not defaulted.

Budget caps (work order): per-request <= $0.10, task total <= $0.50.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

PER_REQUEST_CAP_USD = 0.10
TOTAL_CAP_USD = 0.50

# Currencies we can compare to a USD cap without inventing an FX rate. USDC /
# USDC.e are treated 1:1 with USD (stablecoin). Any other currency is refused
# rather than guessed.
_USD_EQUIVALENT = {"usd", "usdc", "usdc.e"}


@dataclass
class Challenge:
    scheme: str                 # e.g. "tempo", "stripe"
    amount: float | None        # numeric amount, or None if absent
    currency: str | None
    method: str | None          # value of a method="..." attribute, if present
    params: dict[str, str]
    raw: str


def _split_challenges(header_value: str) -> list[str]:
    """Split a www-authenticate value into per-scheme challenge strings.

    A challenge starts with a scheme token (a bare word) followed by
    space-separated `k=v` params. Multiple challenges are comma-separated, but
    commas also separate params, so we split on a comma that immediately
    precedes a new `scheme ` token.
    """
    value = header_value.strip()
    # Insert a sentinel before each ", <scheme> " boundary, then split on it.
    marked = re.sub(r",\s*(?=[A-Za-z][A-Za-z0-9_-]*\s+[A-Za-z])", "\x00", value)
    return [c.strip() for c in marked.split("\x00") if c.strip()]


def parse_challenge(header_value: str) -> list[Challenge]:
    """Parse a `www-authenticate` header value into Challenge objects.

    Raises ValueError on something that does not look like a scheme+params
    challenge at all (do not swallow into an empty list).
    """
    out: list[Challenge] = []
    for chunk in _split_challenges(header_value):
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*)\s+(.*)$", chunk, re.DOTALL)
        if not m:
            # A bare scheme with no params is still a scheme.
            m2 = re.match(r"^([A-Za-z][A-Za-z0-9_-]*)\s*$", chunk)
            if not m2:
                raise ValueError(f"unrecognized challenge segment: {chunk!r}")
            out.append(Challenge(m2.group(1).lower(), None, None, None, {}, chunk))
            continue
        scheme = m.group(1).lower()
        # Params are `k="quoted"` or `k=bareword`. The regex yields (key, quoted,
        # bare); exactly one of quoted/bare is populated per match.
        params: dict[str, str] = {}
        for km, qv, bv in re.findall(r'([A-Za-z0-9_.-]+)=(?:"([^"]*)"|([^\s,]+))', m.group(2)):
            params[km.lower()] = qv if bv == "" else bv
        amount = None
        if "amount" in params:
            try:
                amount = float(params["amount"])
            except ValueError as exc:
                raise ValueError(f"non-numeric amount in challenge {chunk!r}: {exc}")
        out.append(Challenge(
            scheme=scheme,
            amount=amount,
            currency=(params.get("currency") or None),
            method=(params.get("method") or None),
            params=params,
            raw=chunk,
        ))
    if not out:
        raise ValueError(f"no challenges parsed from header value: {header_value!r}")
    return out


def choose_client(challenges: list[Challenge]) -> dict[str, Any]:
    """Pick the mpp-agent client per SKILL.md:30/36/112-113.

    If any challenge advertises `method="stripe"` -> Stripe Link (`link-cli`).
    Otherwise -> `mppx`, which pays the Tempo challenge.
    Returns {client, reason, target_challenge}.
    """
    stripe = next((c for c in challenges if (c.method or "").lower() == "stripe"), None)
    if stripe is not None:
        return {
            "client": "link-cli",
            "reason": 'challenge advertises method="stripe" (SKILL.md:30,112) -> Stripe Link',
            "target_challenge": stripe,
        }
    tempo = next((c for c in challenges if c.scheme == "tempo"), None)
    target = tempo if tempo is not None else challenges[0]
    return {
        "client": "mppx",
        "reason": "no stripe method; mppx pays the Tempo challenge (SKILL.md:36,113)",
        "target_challenge": target,
    }


def check_budget(amount: float | None, currency: str | None, spent_usd: float,
                 per_cap: float = PER_REQUEST_CAP_USD,
                 total_cap: float = TOTAL_CAP_USD) -> dict[str, Any]:
    """Decide whether a payment of `amount` may proceed.

    Zero-amount challenges are allowed (SKILL.md:114). Unknown currency FAILS
    LOUDLY — we do not invent an FX rate to force it under a USD cap.
    """
    if amount is None:
        raise ValueError("challenge has no amount; cannot budget-check (do not assume)")
    if amount == 0:
        return {"decision": "allow", "reason": "zero-amount proof credential (SKILL.md:114)",
                "amount_usd": 0.0}
    cur = (currency or "").lower()
    if cur not in _USD_EQUIVALENT:
        raise ValueError(
            f"currency {currency!r} is not a known USD-equivalent {sorted(_USD_EQUIVALENT)}; "
            f"refusing rather than guessing an FX rate"
        )
    amount_usd = float(amount)  # 1:1 stablecoin/USD
    if amount_usd > per_cap:
        return {"decision": "deny", "reason": f"per-request ${amount_usd:.4f} > cap ${per_cap:.2f}",
                "amount_usd": amount_usd}
    if spent_usd + amount_usd > total_cap:
        return {"decision": "deny",
                "reason": f"would exceed task total: spent ${spent_usd:.4f} + ${amount_usd:.4f} > cap ${total_cap:.2f}",
                "amount_usd": amount_usd}
    return {"decision": "allow", "reason": "within per-request and total caps", "amount_usd": amount_usd}


if __name__ == "__main__":
    import json
    import sys

    header = sys.argv[1] if len(sys.argv) > 1 else 'tempo amount=0.1 currency=USDC'
    spent = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    chs = parse_challenge(header)
    choice = choose_client(chs)
    tc = choice["target_challenge"]
    budget = check_budget(tc.amount, tc.currency, spent)
    print(json.dumps({
        "challenges": [c.__dict__ for c in chs],
        "client": choice["client"],
        "client_reason": choice["reason"],
        "target": tc.raw,
        "budget": budget,
    }, ensure_ascii=False, indent=2))
