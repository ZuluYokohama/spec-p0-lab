import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.g4_bridge import (
    FORBIDDEN_FALLBACKS,
    check_bundle,
    e_h_size,
    e_p99_size,
    example_prereg,
)


def _arm(name, p99_512="NA", h_512=1.23):
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


def test_cardinality_locked_grid():
    assert e_p99_size(512) == 0
    assert e_p99_size(1024) == 512
    assert e_p99_size(2048) == 1536
    assert e_p99_size(4096) == 3584
    assert e_h_size(512) == 512
    assert e_h_size(1024) == 512
    assert e_h_size(4096) == 512


def test_admit_na_at_l512():
    check_bundle(example_prereg(), {"arms": [_arm("QKNORM"), _arm("SPECHARD")]})


def test_reject_finite_p99_l512():
    with pytest.raises(SystemExit) as ei:
        check_bundle(example_prereg(), {"arms": [_arm("QKNORM", p99_512=0.42)]})
    assert ei.value.code == 2


def test_reject_copied_tail():
    with pytest.raises(SystemExit):
        check_bundle(
            example_prereg(),
            {"arms": [_arm("QKNORM", p99_512=1.23, h_512=1.23)]},
        )


def test_reject_missing_prereg_keys():
    bad = example_prereg()
    del bad["empty_p99_policy"]
    with pytest.raises(SystemExit):
        check_bundle(bad, {"arms": [_arm("QKNORM")]})


def test_reject_shifted_cutoff_policy():
    bad = example_prereg()
    bad["empty_p99_policy"] = "use_last_256"
    with pytest.raises(SystemExit):
        check_bundle(bad, {"arms": [_arm("QKNORM")]})


def test_checked_in_prereg_matches_example():
    path = Path(__file__).resolve().parents[1] / "prereg" / "g4_applicability.json"
    on_disk = json.loads(path.read_text())
    assert on_disk["empty_p99_policy"] == "NA"
    assert on_disk["indexing"] == "0-index-[0,L)"
    assert set(on_disk["forbidden_fallbacks"]) == FORBIDDEN_FALLBACKS
    assert on_disk["cardinality"]["512"]["p99"] == 0
