import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.g4_bridge import (
    FORBIDDEN_FALLBACKS,
    check_bundle,
    example_prereg,
    n_H,
    n_p99,
)


def _arm(name, p99_512="inapplicable", h_512=1.23):
    return {
        "name": name,
        "g4_p99": {
            "L512": p99_512,
            "L1024": 0.1,
            "L2048": 0.2,
            "L4096": 0.3,
        },
        "g4_entropy": {
            "L512": h_512,
            "L1024": 1.0,
            "L2048": 1.1,
            "L4096": 1.2,
        },
    }


def test_cardinality_from_prereg_alone():
    z = "0-index-[0,L)"
    o = "1-index-[1,L]"
    assert n_p99(z, 512) == 0
    assert n_p99(o, 512) == 1
    assert n_p99(z, 1024) == 512
    assert n_p99(o, 1024) == 513
    assert n_H(z, 512) == 512
    assert n_H(o, 4096) == 512


def test_admit_inapplicable_at_l512():
    ledger = check_bundle(example_prereg(), {"arms": [_arm("QKNORM"), _arm("SPECHARD")]})
    inc = [r for r in ledger if r["verdict"] == "inapplicable"]
    assert len(inc) == 2  # one p99 L=512 per arm
    assert all(r["reason"] == "empty_applicability_set_declared" for r in inc)
    assert all(r["declared"] for r in inc)


def test_reject_vacuous_pass():
    with pytest.raises(SystemExit) as ei:
        check_bundle(example_prereg(), {"arms": [_arm("QKNORM", p99_512="pass")]})
    assert ei.value.code == 2


def test_reject_finite_p99_l512_zero_index():
    with pytest.raises(SystemExit):
        check_bundle(example_prereg(), {"arms": [_arm("QKNORM", p99_512=0.42)]})


def test_one_index_l512_is_applicable():
    pr = example_prereg("1-index-[1,L]")
    assert pr["cardinality_declared_now"]["512"]["p99"] == 1
    ledger = check_bundle(pr, {"arms": [_arm("QKNORM", p99_512=0.42)]})
    row = next(r for r in ledger if r["stat"] == "g4_p99" and r["L"] == 512)
    assert row["verdict"] == "pass"
    assert row["n_eligible"] == 1


def test_reject_undeclared_schema():
    bad = example_prereg()
    del bad["empty_set_verdict"]
    with pytest.raises(SystemExit):
        check_bundle(bad, {"arms": [_arm("QKNORM")]})


def test_checked_in_prereg():
    path = Path(__file__).resolve().parents[1] / "prereg" / "g4_applicability.json"
    on_disk = json.loads(path.read_text())
    assert on_disk["indexing"] == "0-index-[0,L)"
    assert on_disk["empty_set_verdict"] == "inapplicable"
    assert set(on_disk["forbidden_fallbacks"]) == FORBIDDEN_FALLBACKS
    assert on_disk["cardinality_declared_now"]["512"]["p99"] == 0
