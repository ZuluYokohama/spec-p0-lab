from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from round2_bridge.canonical import sha256_file, sha256_obj
from round2_bridge.models import (
    ENTROPY_REGION,
    FORBIDDEN_NOUNS,
    G4_ARMS,
    L4096_P99_MINUS_H,
    LOCKED_L,
    P99_REGION,
    Report,
    Status,
    bundle_layout,
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")
NOUN_SPLIT = re.compile(
    r"constrained\s*[\n`*_>#-]*\s*mixers?",
    re.I,
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _git(repo: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    return p.returncode, (p.stdout + p.stderr).strip()


def validate(bundle_root: Path, repo: Path | None) -> Report:
    r = Report(status=Status.INCOMPLETE)
    paths = bundle_layout(bundle_root)

    missing = [k for k, p in paths.items() if not p.exists()]
    # verdict and findings may be absent → normative adjudication, not reject
    optional = {"verdict", "findings", "claims"}
    req_missing = [k for k in missing if k not in optional]
    if req_missing:
        r.add("MISSING_ARTIFACT", "incomplete", f"missing {req_missing}")
        if any(
            k in req_missing
            for k in ("lock", "eval_norm_py", "gate_spec", "matrix", "region")
        ):
            r.finalize()
            return r

    if paths["lock"].exists():
        r.bindings["lock_sha256"] = sha256_file(str(paths["lock"]))
    if paths["eval_norm_py"].exists():
        r.bindings["eval_norm_py_sha256"] = sha256_file(str(paths["eval_norm_py"]))
    if paths["gate_spec"].exists():
        r.bindings["gate_spec_sha256"] = sha256_file(str(paths["gate_spec"]))

    if paths["gate_spec"].exists():
        gs = _load(paths["gate_spec"])
        ver = gs.get("g1_g3_version")
        ptr = gs.get("g1_g3_pointer")
        h = gs.get("g1_g3_hash")
        if not ver or not ptr or not (isinstance(h, str) and HEX64.match(h)):
            r.add(
                "GATE_UNPINNED",
                "reject",
                "G1-G3 must be pinned by version, pointer, and 64-hex hash",
            )
        if gs.get("selected_after_results"):
            r.add("GATE_VERSION_DRIFT", "reject", "bridge must not choose v1.1 vs v1.2 after results")

    if paths["region"].exists():
        pol = _load(paths["region"])
        _check_region(pol, r)

    if paths["matrix"].exists() and paths["eval_jsonl"].exists():
        _check_matrix(_load(paths["matrix"]), _jsonl(paths["eval_jsonl"]), r)
    elif not paths["eval_jsonl"].exists():
        r.add("NO_EVAL", "incomplete", "evidence/eval_norm.jsonl missing")

    if paths["g4_commit"].exists():
        r.bindings["g4_commitment_sha256"] = sha256_file(str(paths["g4_commit"]))
    if paths["g1g3"].exists():
        r.bindings["g1_g3_sha256"] = sha256_file(str(paths["g1g3"]))
        g13 = _load(paths["g1g3"])
        if paths["gate_spec"].exists():
            gs = _load(paths["gate_spec"])
            if g13.get("g1_g3_hash") and g13.get("g1_g3_hash") != gs.get("g1_g3_hash"):
                r.add("GATE_VERSION_DRIFT", "reject", "g1_g3 record hash != gate_spec hash")
    else:
        r.add("NO_G1G3", "incomplete", "adjudication/g1_g3.json missing")

    if paths["g4_seal"].exists():
        r.bindings["g4_prereveal_sha256"] = sha256_file(str(paths["g4_seal"]))
        if not paths["g1g3"].exists():
            r.add("PREMATURE_REVEAL", "reject", "prereveal seal without G1-G3 record")
    else:
        r.add("NO_SEAL", "incomplete", "blind_g4/prereveal_lock.json missing")

    if paths["g4_reveal"].exists():
        if not paths["g4_seal"].exists() or not paths["g4_commit"].exists():
            r.add("PREMATURE_REVEAL", "reject", "reveal before commitment+seal")
        else:
            _check_reveal(
                _load(paths["g4_commit"]),
                _load(paths["g4_seal"]),
                _load(paths["g4_reveal"]),
                r,
            )
        r.bindings["g4_reveal_sha256"] = sha256_file(str(paths["g4_reveal"]))
    else:
        r.add("NO_REVEAL", "incomplete", "blind_g4/reveal.json missing")

    _scan_nouns(bundle_root, r)

    if paths["verdict"].exists():
        r.bindings["verdict_sha256"] = sha256_file(str(paths["verdict"]))
        v = _load(paths["verdict"])
        need = [
            "lock_sha256",
            "eval_norm_py_sha256",
            "g1_g3_sha256",
            "g4_prereveal_sha256",
            "g4_reveal_sha256",
        ]
        for k in need:
            if v.get(k) != r.bindings.get(k):
                r.add(
                    "BINDING_MISMATCH",
                    "reject",
                    f"verdict.{k} does not match computed binding",
                )
        if v.get("status") not in {
            "SCOPED_PASS",
            "SCOPED_FAIL",
            "SCOPED_INCONCLUSIVE",
            "INAPPLICABLE",
        }:
            r.add("UNSCOPED_VERDICT", "reject", "verdict status is not a scoped token")

    if repo is None:
        r.add("NO_REPO", "incomplete", "--repo required for independent ancestry check")
    else:
        _check_repo(repo, paths, r)

    r.finalize()
    return r


def _check_region(pol: dict, r: Report) -> None:
    need = [
        "indexing",
        "valid_token_coordinates",
        "query_axis",
        "reduction_order",
        "padding_and_mask",
        "quantile_method",
        "nan_policy",
        "layer_head_reduction",
        "l512_p99_branch",
        "p99_region",
        "entropy_region",
    ]
    miss = [k for k in need if k not in pol]
    if miss:
        r.add("REGION_UNPINNED", "reject", f"g4_region_policy missing {miss}")
        return
    if pol.get("p99_region") != P99_REGION:
        r.add("WRONG_P99_REGION", "reject", f"p99_region {pol.get('p99_region')!r} != {P99_REGION!r}")
    if pol.get("entropy_region") != ENTROPY_REGION:
        r.add("WRONG_H_REGION", "reject", f"entropy_region {pol.get('entropy_region')!r}")
    card = pol.get("cardinality") or {}
    p99_4096 = card.get("4096", {}).get("p99")
    h_4096 = card.get("4096", {}).get("entropy")
    if p99_4096 is None or h_4096 is None or int(p99_4096) - int(h_4096) != L4096_P99_MINUS_H:
        r.add(
            "L4096_REGION_CONTRADICTION",
            "reject",
            "L=4096 |E_p99|-|E_H| must be 3072",
        )
    branch = pol.get("l512_p99_branch")
    if branch not in {"NOT_EVALUABLE", "EXCLUDED_BY_LOCKED_RULE"}:
        r.add(
            "L512_UNRESOLVED",
            "reject",
            "L=512 p99 branch must be NOT_EVALUABLE or EXCLUDED_BY_LOCKED_RULE",
        )
    if pol.get("indexing") not in {"0-index-[0,L)", "1-index-[1,L]"}:
        r.add("INDEXING_UNDECLARED", "reject", "indexing must be first-class")
    if pol.get("nan_policy") in {"drop", "impute", "skip"}:
        r.add("NAN_LAUNDER", "reject", "NaN-drop/impute is vacuity laundered into a pass")


def _check_matrix(matrix: dict, rows: list[dict], r: Report) -> None:
    arms = list(matrix.get("arms") or [])
    lengths = list(matrix.get("lengths") or [])
    if tuple(lengths) != LOCKED_L:
        r.add("MATRIX_L", "reject", f"lengths must be {LOCKED_L}")
    expected = {(a, int(L)) for a in arms for L in LOCKED_L}
    seen: set[tuple[str, int]] = set()
    for row in rows:
        if row.get("namespace") not in (None, "confirmatory"):
            r.add("EXPLORATORY_IN_EVIDENCE", "reject", "exploratory row in eval_norm.jsonl")
            continue
        key = (row.get("arm"), int(row.get("L", -1)))
        if key in seen:
            r.add("DUP_CELL", "reject", f"duplicate cell {key}")
        seen.add(key)
        if key not in expected:
            r.add("UNEXPECTED_CELL", "reject", f"unexpected cell {key}")
    miss = expected - seen
    if miss:
        r.add("MISSING_CELL", "reject", f"missing confirmatory cells {sorted(miss)[:12]}")
    # L=512 p99 must not be a finite pass token
    for row in rows:
        if int(row.get("L", -1)) == 512:
            p99 = row.get("g4_p99")
            if p99 not in (None, "NOT_EVALUABLE", "INAPPLICABLE", "EXCLUDED"):
                if isinstance(p99, (int, float)):
                    r.add(
                        "L512_FINITE_P99",
                        "reject",
                        "finite G4-p99 at L=512 is not licensed by empty-set policy",
                    )


def _check_reveal(commit: dict, seal: dict, reveal: dict, r: Report) -> None:
    if commit.get("payload_sha256") and seal.get("commitment_sha256") not in {
        commit.get("payload_sha256"),
        None,
    }:
        if seal.get("commitment_sha256") != commit.get("sha256") and seal.get(
            "commitment_sha256"
        ) != commit.get("payload_sha256"):
            r.add("G4_COMMIT_MISMATCH", "reject", "prereveal seal does not bind commitment")
    mapping = reveal.get("mapping") or {}
    ids = set(mapping.keys())
    names = set(mapping.values())
    if names != set(G4_ARMS) or len(ids) != 2:
        r.add(
            "REVEAL_NOT_BIJECTIVE",
            "reject",
            "reveal must map exactly two opaque ids onto {QKNORM, SPECHARD}",
        )
    if reveal.get("committed_payload_sha256") and commit.get("payload_sha256"):
        if reveal["committed_payload_sha256"] != commit["payload_sha256"]:
            r.add("G4_COMMIT_MISMATCH", "reject", "reveal payload hash != commitment")


def _scan_nouns(root: Path, r: Report) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".json", ".jsonl", ".txt", ".rst"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if NOUN_SPLIT.search(text):
            r.add(
                "NOUN_LEAK",
                "reject",
                f"delegated noun leak in {path.relative_to(root)}",
            )
        low = text.lower()
        for noun in FORBIDDEN_NOUNS:
            if noun in low:
                r.add("NOUN_LEAK", "reject", f"{noun!r} in {path.relative_to(root)}")


def _check_repo(repo: Path, paths: dict, r: Report) -> None:
    code, out = _git(repo, "rev-parse", "HEAD")
    if code != 0:
        r.add("REPO_UNVERIFIED", "incomplete", f"git rev-parse failed: {out}")
        return
    r.bindings["repo_head"] = out.split()[0]
    code, _ = _git(repo, "rev-parse", "--is-inside-work-tree")
    if code != 0:
        r.add("REPO_UNVERIFIED", "incomplete", "--repo is not a git work tree")
    if paths["lock"].exists():
        lock = _load(paths["lock"])
        expected = lock.get("repo_head") or lock.get("commit")
        if expected and expected != r.bindings["repo_head"]:
            r.add(
                "REPO_DRIFT",
                "reject",
                f"lock.repo_head {expected} != verified HEAD {r.bindings['repo_head']}",
            )
