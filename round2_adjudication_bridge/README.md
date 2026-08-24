# Round-2 Adjudication Bridge

Fail-closed evidence intake for the locked round-2 norm experiment.
Does not restate G1–G4 thresholds, modify the preregistration, submit GPU
jobs, or promote a scientific claim.

Current evidence state: **USER_REPORTED_NOT_YET_INSPECTED**.
The 0.90 → 0.92 → 0.97 review is a claim-governance pass, not a model-result pass.

## Use

```bash
PYTHONPATH=src python -m round2_bridge validate /path/to/round2_bundle --repo /path/to/source-repo
PYTHONPATH=src python -m round2_bridge commit-json blind_g4/committed_payload.json
PYTHONPATH=src python -m round2_bridge render-hf-job hf/job_request.json
PYTHONPATH=src python -m unittest discover -s tests -v
```

Exit 0 = READY_FOR_SIGNOFF or READY_FOR_NORMATIVE_ADJUDICATION.
Exit 2 = INCOMPLETE. Exit 3 = REJECTED. Exit 4 = CLI error.

`eval_norm.py` is normative. FINDINGS.md is narrative only.
