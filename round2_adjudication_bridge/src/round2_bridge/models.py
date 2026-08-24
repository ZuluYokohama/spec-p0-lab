from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

LOCKED_L = (512, 1024, 2048, 4096)
G4_ARMS = ("QKNORM", "SPECHARD")
P99_REGION = "q >= 512"
ENTROPY_REGION = "(L-512, L)"
L4096_P99_MINUS_H = 3072
FORBIDDEN_NOUNS = ("constrained mixers", "constrained mixer", "lever")


class Status(str, Enum):
    READY_FOR_SIGNOFF = "READY_FOR_SIGNOFF"
    READY_FOR_NORMATIVE_ADJUDICATION = "READY_FOR_NORMATIVE_ADJUDICATION"
    INCOMPLETE = "INCOMPLETE"
    REJECTED = "REJECTED"
    CLI_ERROR = "CLI_ERROR"


EXIT = {
    Status.READY_FOR_SIGNOFF: 0,
    Status.READY_FOR_NORMATIVE_ADJUDICATION: 0,
    Status.INCOMPLETE: 2,
    Status.REJECTED: 3,
    Status.CLI_ERROR: 4,
}


@dataclass
class Finding:
    code: str
    severity: str  # reject | incomplete | note
    message: str


@dataclass
class Report:
    status: Status
    findings: list[Finding] = field(default_factory=list)
    bindings: dict[str, str] = field(default_factory=dict)
    ledger: list[dict] = field(default_factory=list)

    def add(self, code: str, severity: str, message: str) -> None:
        self.findings.append(Finding(code, severity, message))

    def finalize(self) -> Status:
        if any(f.severity == "reject" for f in self.findings):
            self.status = Status.REJECTED
        elif any(f.severity == "incomplete" for f in self.findings):
            self.status = Status.INCOMPLETE
        elif self.bindings.get("verdict_sha256"):
            self.status = Status.READY_FOR_SIGNOFF
        else:
            self.status = Status.READY_FOR_NORMATIVE_ADJUDICATION
        return self.status


def bundle_layout(root: Path) -> dict[str, Path]:
    return {
        "bundle": root / "bundle.json",
        "lock": root / "prereg" / "lock.json",
        "eval_norm_py": root / "prereg" / "eval_norm.py",
        "closure": root / "prereg" / "execution_closure.json",
        "gate_spec": root / "prereg" / "gate_spec.json",
        "matrix": root / "prereg" / "expected_matrix.json",
        "region": root / "prereg" / "g4_region_policy.json",
        "precedence": root / "prereg" / "claim_precedence.json",
        "terminology": root / "prereg" / "terminology_policy.json",
        "eval_jsonl": root / "evidence" / "eval_norm.jsonl",
        "g1g3": root / "adjudication" / "g1_g3.json",
        "verdict": root / "adjudication" / "round2_verdict.json",
        "g4_commit": root / "blind_g4" / "commitment.json",
        "g4_seal": root / "blind_g4" / "prereveal_lock.json",
        "g4_reveal": root / "blind_g4" / "reveal.json",
        "claims": root / "claims" / "claims.jsonl",
        "findings": root / "report" / "FINDINGS.md",
    }
