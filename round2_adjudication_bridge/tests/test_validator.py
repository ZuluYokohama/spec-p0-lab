from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from round2_bridge.canonical import sha256_obj  # noqa: E402
from round2_bridge.hf_render import render  # noqa: E402
from round2_bridge.models import Status  # noqa: E402
from round2_bridge.validator import validate  # noqa: E402

ARMS = ["BASE", "QKNORM", "SPECHARD"]
LENGTHS = [512, 1024, 2048, 4096]
GATE_HASH = "a" * 64
RUNNER = "b" * 64


def _write(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, str):
        p.write_text(obj)
    else:
        p.write_text(json.dumps(obj, indent=2) + "\n")


def _git_init(repo: Path) -> str:
    subprocess.check_call(["git", "init"], cwd=repo, stdout=subprocess.DEVNULL)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    (repo / "README").write_text("x\n")
    subprocess.check_call(["git", "add", "."], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "i"], cwd=repo, stdout=subprocess.DEVNULL)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def _region(good=True, l512="NOT_EVALUABLE", p99="q >= 512", ent="(L-512, L)") -> dict:
    card = {
        "512": {"p99": 0, "entropy": 512},
        "1024": {"p99": 512, "entropy": 512},
        "2048": {"p99": 1536, "entropy": 512},
        "4096": {"p99": 3584 if good else 3584, "entropy": 512 if good else 512},
    }
    if not good:
        card["4096"]["entropy"] = 512
        card["4096"]["p99"] = 512  # difference 0, not 3072
    return {
        "indexing": "0-index-[0,L)",
        "valid_token_coordinates": "[0, L)",
        "query_axis": "query_position",
        "reduction_order": "query_then_head_then_layer",
        "padding_and_mask": "exclude_pad",
        "quantile_method": "linear",
        "nan_policy": "propagate_as_inapplicable",
        "layer_head_reduction": "mean_over_heads_then_layers",
        "l512_p99_branch": l512,
        "p99_region": p99,
        "entropy_region": ent,
        "cardinality": card,
    }


def _rows() -> list[dict]:
    out = []
    for a in ARMS:
        for L in LENGTHS:
            row = {
                "namespace": "confirmatory",
                "arm": a,
                "L": L,
                "bpb": 1.0,
                "g4_entropy": 3.0,
                "g4_p99": "NOT_EVALUABLE" if L == 512 else 0.1,
            }
            out.append(row)
    return out


def _good_bundle(tmp: Path, repo_head: str) -> Path:
    root = tmp / "round2_bundle"
    payload = {"blind": ["idA", "idB"], "metric": "g4"}
    payload_sha = sha256_obj(payload)
    _write(root / "bundle.json", {"schema": "round2.bundle.v1"})
    _write(root / "prereg" / "lock.json", {"repo_head": repo_head, "commit": repo_head})
    _write(root / "prereg" / "eval_norm.py", "# locked eval_norm stub\nprint('normative')\n")
    _write(root / "prereg" / "execution_closure.json", {"python": "3.12", "cmd": ["python", "eval_norm.py"]})
    _write(
        root / "prereg" / "gate_spec.json",
        {
            "g1_g3_version": "v1.2",
            "g1_g3_pointer": "prereg/gates.md#v1.2",
            "g1_g3_hash": GATE_HASH,
            "selected_after_results": False,
        },
    )
    _write(root / "prereg" / "expected_matrix.json", {"arms": ARMS, "lengths": LENGTHS})
    _write(root / "prereg" / "g4_region_policy.json", _region())
    _write(root / "prereg" / "claim_precedence.json", {"rule": "gates > instrument > findings"})
    _write(
        root / "prereg" / "terminology_policy.json",
        {"licensed_noun": "sigma-reparam", "forbidden": ["constrained mixers"]},
    )
    (root / "evidence").mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(x) for x in _rows()]
    (root / "evidence" / "eval_norm.jsonl").write_text("\n".join(lines) + "\n")
    _write(
        root / "adjudication" / "g1_g3.json",
        {"g1_g3_hash": GATE_HASH, "G1": "pending", "G2": "pending", "G3": "pending"},
    )
    _write(
        root / "blind_g4" / "commitment.json",
        {"payload_sha256": payload_sha, "sha256": payload_sha},
    )
    _write(root / "blind_g4" / "prereveal_lock.json", {"commitment_sha256": payload_sha})
    _write(
        root / "blind_g4" / "reveal.json",
        {
            "mapping": {"idA": "QKNORM", "idB": "SPECHARD"},
            "committed_payload_sha256": payload_sha,
        },
    )
    _write(root / "claims" / "claims.jsonl", "")
    _write(root / "report" / "FINDINGS.md", "Narrative only. Licensed noun: sigma-reparam.\n")
    return root


class ValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.id().replace(".", "_"))
        # unittest cwd varies; use isolated tmp under tests/_out
        self.base = ROOT / "tests" / "_out" / self._testMethodName
        if self.base.exists():
            import shutil

            shutil.rmtree(self.base)
        self.base.mkdir(parents=True)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.head = _git_init(self.repo)
        self.bundle = _good_bundle(self.base, self.head)

    def test_end_to_end_ready_for_adjudication(self) -> None:
        report = validate(self.bundle, self.repo)
        self.assertIn(
            report.status,
            {Status.READY_FOR_NORMATIVE_ADJUDICATION, Status.READY_FOR_SIGNOFF},
        )
        codes = {f.code for f in report.findings if f.severity != "note"}
        self.assertNotIn("WRONG_P99_REGION", codes)

    def test_wrong_p99_region(self) -> None:
        _write(self.bundle / "prereg" / "g4_region_policy.json", _region(p99="last-512"))
        report = validate(self.bundle, self.repo)
        self.assertEqual(report.status, Status.REJECTED)
        self.assertTrue(any(f.code == "WRONG_P99_REGION" for f in report.findings))

    def test_l4096_contradiction(self) -> None:
        _write(self.bundle / "prereg" / "g4_region_policy.json", _region(good=False))
        report = validate(self.bundle, self.repo)
        self.assertTrue(any(f.code == "L4096_REGION_CONTRADICTION" for f in report.findings))

    def test_unresolved_l512(self) -> None:
        _write(self.bundle / "prereg" / "g4_region_policy.json", _region(l512="decide_later"))
        report = validate(self.bundle, self.repo)
        self.assertTrue(any(f.code == "L512_UNRESOLVED" for f in report.findings))

    def test_noun_leak_markdown_split(self) -> None:
        cited = self.bundle / "report" / "cited.md"
        cited.write_text("the constrained\nmixers are untested\n")
        report = validate(self.bundle, self.repo)
        self.assertTrue(any(f.code == "NOUN_LEAK" for f in report.findings))

    def test_gate_version_drift(self) -> None:
        g = json.loads((self.bundle / "adjudication" / "g1_g3.json").read_text())
        g["g1_g3_hash"] = "c" * 64
        _write(self.bundle / "adjudication" / "g1_g3.json", g)
        report = validate(self.bundle, self.repo)
        self.assertTrue(any(f.code == "GATE_VERSION_DRIFT" for f in report.findings))

    def test_premature_reveal(self) -> None:
        (self.bundle / "blind_g4" / "prereveal_lock.json").unlink()
        report = validate(self.bundle, self.repo)
        self.assertTrue(
            any(f.code in {"PREMATURE_REVEAL", "NO_SEAL"} for f in report.findings)
        )

    def test_g4_commit_mismatch(self) -> None:
        rev = json.loads((self.bundle / "blind_g4" / "reveal.json").read_text())
        rev["committed_payload_sha256"] = "d" * 64
        _write(self.bundle / "blind_g4" / "reveal.json", rev)
        report = validate(self.bundle, self.repo)
        self.assertTrue(any(f.code == "G4_COMMIT_MISMATCH" for f in report.findings))

    def test_missing_repo(self) -> None:
        report = validate(self.bundle, None)
        self.assertEqual(report.status, Status.INCOMPLETE)
        self.assertTrue(any(f.code == "NO_REPO" for f in report.findings))

    def test_unpinned_hf_url(self) -> None:
        out = render(
            {
                "frozen_spec_digest": "a" * 64,
                "spec_url": "https://huggingface.co/org/spec/blob/main/job.py",
                "runner_digest": RUNNER,
                "hardware_flavor": "a10g-small",
                "timeout_seconds": 3600,
                "hourly_price_usd": 1.0,
                "timeout_hours": 1.0,
                "max_cost_usd": 5.0,
                "secret_names": ["HF_TOKEN"],
            }
        )
        self.assertFalse(out["ok"])
        self.assertTrue(any("resolve" in e for e in out["errors"]))

    def test_cost_cap(self) -> None:
        out = render(
            {
                "frozen_spec_digest": "a" * 64,
                "spec_url": "https://huggingface.co/org/spec/resolve/abcdef1/job.py",
                "runner_digest": RUNNER,
                "hardware_flavor": "a10g-small",
                "timeout_seconds": 3600,
                "hourly_price_usd": 10.0,
                "timeout_hours": 3.0,
                "max_cost_usd": 5.0,
                "secret_names": ["HF_TOKEN"],
            }
        )
        self.assertFalse(out["ok"])
        self.assertTrue(any("cost-cap" in e for e in out["errors"]))

    def test_secret_leakage(self) -> None:
        out = render(
            {
                "frozen_spec_digest": "a" * 64,
                "spec_url": "https://huggingface.co/org/spec/resolve/abcdef1/job.py",
                "runner_digest": RUNNER,
                "hardware_flavor": "a10g-small",
                "timeout_seconds": 3600,
                "hourly_price_usd": 1.0,
                "timeout_hours": 1.0,
                "max_cost_usd": 5.0,
                "secret_names": ["HF_TOKEN"],
                "hf_token": "hf_leaked",
            }
        )
        self.assertFalse(out["ok"])
        self.assertTrue(any("secret-value" in e for e in out["errors"]))


if __name__ == "__main__":
    unittest.main()
