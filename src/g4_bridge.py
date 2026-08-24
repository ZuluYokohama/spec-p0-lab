"""G4 eval bridge.

Indexing is a first-class prereg field. Eligibility is computed from the
prereg alone, before any data exists. Empty applicability is INAPPLICABLE,
never PASS. Vacuous ∀x∈∅ is the bug class; NaN-drop is vacuity laundered
into a pass.

Usage:
    python -m src.g4_bridge --prereg path.json --bundle path.json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Literal

Indexing = Literal["0-index-[0,L)", "1-index-[1,L]"]
Verdict = Literal["pass", "fail", "inapplicable"]

ALLOWED_INDEXING: tuple[Indexing, ...] = ("0-index-[0,L)", "1-index-[1,L]")
LOCKED_L = (512, 1024, 2048, 4096)
CUTOFF = 512
FORBIDDEN_FALLBACKS = {
    "drop_nan",
    "tail512",
    "use_entropy_set",
    "reindex_after_unblind",
    "shift_cutoff",
    "impute",
    "vacuous_pass",
}
REQUIRED_PREREG_KEYS = (
    "indexing",
    "E_p99_rule",
    "E_H_rule",
    "empty_set_verdict",
    "forbidden_fallbacks",
)


def n_p99(indexing: str, L: int) -> int:
    """|E_p99(L)| from the prereg convention. No data."""
    if indexing == "0-index-[0,L)":
        # positions 0..L-1; q >= 512
        return max(0, L - CUTOFF)
    if indexing == "1-index-[1,L]":
        # positions 1..L; q >= 512 → {512,...,L}
        return max(0, L - CUTOFF + 1)
    raise ValueError(indexing)


def n_H(indexing: str, L: int) -> int:
    """|E_H(L)| last-min(L,512) positions under the same convention."""
    del indexing
    return min(L, CUTOFF)


def reject(msg: str) -> None:
    print(f"REJECT: {msg}", file=sys.stderr)
    raise SystemExit(2)


def check_prereg(prereg: dict[str, Any]) -> None:
    missing = [k for k in REQUIRED_PREREG_KEYS if k not in prereg]
    if missing:
        reject(
            f"undeclared applicability schema {missing}; "
            "eligibility is not an edge case to discover at runtime"
        )
    if prereg["indexing"] not in ALLOWED_INDEXING:
        reject(f"indexing must be one of {ALLOWED_INDEXING}, got {prereg['indexing']!r}")
    if prereg["E_p99_rule"] != "q >= 512":
        reject(f"E_p99_rule drift: {prereg['E_p99_rule']!r}")
    if prereg["E_H_rule"] != "q >= L-512":
        reject(f"E_H_rule drift: {prereg['E_H_rule']!r}")
    if prereg["empty_set_verdict"] != "inapplicable":
        reject(
            f"empty_set_verdict must be 'inapplicable' (not pass, not NA-as-pass); "
            f"got {prereg['empty_set_verdict']!r}"
        )
    fb = set(prereg.get("forbidden_fallbacks", []))
    if not FORBIDDEN_FALLBACKS.issubset(fb):
        reject(f"forbidden_fallbacks must cover {sorted(FORBIDDEN_FALLBACKS)}")


def cell_verdict(value: Any, n: int) -> tuple[Verdict, str]:
    """Three-valued. Empty set cannot be pass."""
    if n == 0:
        if value in {"inapplicable", "NA", "I"}:
            return "inapplicable", "empty_applicability_set_declared"
        if value in {"pass", True}:
            return "fail", "vacuous_pass_on_empty_set"
        return "fail", f"empty_set_reported_as {value!r}"
    if value in {"inapplicable", "NA", "I"}:
        return "fail", f"marked_inapplicable_but_n={n}"
    if value is None:
        return "fail", "null_is_nan_drop"
    return "pass", "applicable_numeric_cell"
    # numeric vs threshold is the experiment's job; the bridge only
    # licenses that a number is allowed to exist.


def ledger_row(
    arm: str, stat: str, L: int, n: int, value: Any, declared: bool
) -> dict[str, Any]:
    verdict, reason = cell_verdict(value, n)
    return {
        "arm": arm,
        "stat": stat,
        "L": L,
        "n_eligible": n,
        "verdict": verdict,
        "reason": reason,
        "declared": declared,
        "reported": value if value in {"inapplicable", "NA", "I", "pass", "fail"} else "numeric",
    }


def check_bundle(prereg: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    check_prereg(prereg)
    idx = prereg["indexing"]
    declared = True
    arms = bundle.get("arms")
    if not arms:
        reject("bundle has no arms")
    ledger: list[dict[str, Any]] = []
    for arm in arms:
        name = arm.get("name", "?")
        for L in LOCKED_L:
            p99 = arm.get("g4_p99", {}).get(f"L{L}", None)
            h = arm.get("g4_entropy", {}).get(f"L{L}", None)
            row_p = ledger_row(name, "g4_p99", L, n_p99(idx, L), p99, declared)
            row_h = ledger_row(name, "g4_entropy", L, n_H(idx, L), h, declared)
            ledger.extend([row_p, row_h])
            if row_p["reason"] == "vacuous_pass_on_empty_set":
                reject(f"{name} L={L} G4-p99: vacuous pass on empty set")
            if row_p["verdict"] == "fail" and n_p99(idx, L) == 0:
                reject(
                    f"{name} L={L} G4-p99 must be inapplicable "
                    f"(|E|={n_p99(idx, L)} under {idx}); {row_p['reason']}"
                )
            if row_p["verdict"] == "fail" and n_p99(idx, L) > 0 and p99 in {"inapplicable", "NA", "I", None}:
                reject(
                    f"{name} L={L} G4-p99 applicable (|E|={n_p99(idx, L)}) "
                    f"but {row_p['reason']}"
                )
            if row_h["verdict"] == "fail" and n_H(idx, L) > 0 and h in {"inapplicable", "NA", "I", None}:
                reject(f"{name} L={L} G4-entropy {row_h['reason']}")
    return ledger


def example_prereg(indexing: Indexing = "0-index-[0,L)") -> dict[str, Any]:
    return {
        "indexing": indexing,
        "E_p99_rule": "q >= 512",
        "E_H_rule": "q >= L-512",
        "empty_set_verdict": "inapplicable",
        "forbidden_fallbacks": sorted(FORBIDDEN_FALLBACKS),
        "cardinality_declared_now": {
            str(L): {"p99": n_p99(indexing, L), "entropy": n_H(indexing, L)}
            for L in LOCKED_L
        },
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--prereg", required=True)
    p.add_argument("--bundle", required=True)
    args = p.parse_args()
    prereg = json.loads(open(args.prereg).read())
    bundle = json.loads(open(args.bundle).read())
    ledger = check_bundle(prereg, bundle)
    n_i = sum(1 for r in ledger if r["verdict"] == "inapplicable")
    n_p = sum(1 for r in ledger if r["verdict"] == "pass")
    n_f = sum(1 for r in ledger if r["verdict"] == "fail")
    out = {
        "admit": True,
        "indexing": prereg["indexing"],
        "counts": {"pass": n_p, "fail": n_f, "inapplicable": n_i},
        "ledger": ledger,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
