"""Eval-bridge guard for G4 applicability.

Rejects a results bundle unless the prereg already declares the L=512
empty-set branch and the bundle obeys it.

Usage:
    python -m src.g4_bridge --prereg path.json --bundle path.json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

REQUIRED_PREREG_KEYS = (
    "indexing",
    "E_p99",
    "E_H",
    "empty_p99_policy",
)

ALLOWED_EMPTY_POLICY = "NA"
FORBIDDEN_FALLBACKS = {
    "drop_nan",
    "tail512",
    "use_entropy_set",
    "reindex_1based",
    "shift_cutoff",
    "impute",
}

LOCKED_L = (512, 1024, 2048, 4096)


def e_p99_size(L: int) -> int:
    # |{q in [0, L) : q >= 512}|
    return max(0, L - 512)


def e_h_size(L: int) -> int:
    # |{q in [0, L) : q >= L-512}|
    return min(L, 512)


def reject(msg: str) -> None:
    print(f"REJECT: {msg}", file=sys.stderr)
    raise SystemExit(2)


def check_prereg(prereg: dict[str, Any]) -> None:
    missing = [k for k in REQUIRED_PREREG_KEYS if k not in prereg]
    if missing:
        reject(f"prereg missing applicability keys {missing}")
    if prereg["indexing"] not in {"0-index-[0,L)", "0-indexed half-open [0, L)"}:
        reject(f"undeclared/unsupported indexing {prereg['indexing']!r}")
    if prereg["E_p99"] != "q >= 512 in [0, L)":
        reject(f"E_p99 definition drift: {prereg['E_p99']!r}")
    if prereg["E_H"] != "q >= L-512 in [0, L)":
        reject(f"E_H definition drift: {prereg['E_H']!r}")
    if prereg["empty_p99_policy"] != ALLOWED_EMPTY_POLICY:
        reject(
            f"empty_p99_policy must be 'NA', got {prereg['empty_p99_policy']!r}"
        )
    fallbacks = set(prereg.get("forbidden_fallbacks", []))
    if not FORBIDDEN_FALLBACKS.issubset(fallbacks):
        reject(
            "prereg must list forbidden_fallbacks covering "
            f"{sorted(FORBIDDEN_FALLBACKS)}"
        )


def _cell(arm: dict[str, Any], L: int, stat: str) -> Any:
    key = f"L{L}"
    block = arm.get(stat)
    if not isinstance(block, dict) or key not in block:
        reject(f"arm {arm.get('name')!r} missing {stat}.{key}")
    return block[key]


def check_bundle(prereg: dict[str, Any], bundle: dict[str, Any]) -> None:
    check_prereg(prereg)
    arms = bundle.get("arms")
    if not arms:
        reject("bundle has no arms")
    for arm in arms:
        name = arm.get("name", "?")
        p99_512 = _cell(arm, 512, "g4_p99")
        if p99_512 != "NA":
            reject(
                f"{name} G4-p99 L=512 must be NA (|E_p99|=0); got {p99_512!r}"
            )
        for L in LOCKED_L:
            if e_p99_size(L) == 0:
                continue
            val = _cell(arm, L, "g4_p99")
            if val == "NA":
                reject(f"{name} G4-p99 L={L} is applicable (|E|={e_p99_size(L)}) but marked NA")
            if val is None:
                reject(f"{name} G4-p99 L={L} is None; drop/impute is forbidden")
        h512 = _cell(arm, 512, "g4_entropy")
        if h512 == "NA":
            reject(f"{name} G4-entropy L=512 is applicable (|E_H|=512) but marked NA")
        # identity check: do not allow p99 L=512 to equal entropy by sneaking a number
        if arm["g4_p99"]["L512"] == arm["g4_entropy"]["L512"] and arm["g4_p99"]["L512"] != "NA":
            reject(f"{name} G4-p99 L=512 copied entropy/tail")


def example_prereg() -> dict[str, Any]:
    return {
        "indexing": "0-index-[0,L)",
        "E_p99": "q >= 512 in [0, L)",
        "E_H": "q >= L-512 in [0, L)",
        "empty_p99_policy": "NA",
        "forbidden_fallbacks": sorted(FORBIDDEN_FALLBACKS),
        "first_applicable_p99_L": 1024,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--prereg", required=True)
    p.add_argument("--bundle", required=True)
    args = p.parse_args()
    prereg = json.loads(open(args.prereg).read())
    bundle = json.loads(open(args.bundle).read())
    check_bundle(prereg, bundle)
    print("ADMIT")


if __name__ == "__main__":
    main()
