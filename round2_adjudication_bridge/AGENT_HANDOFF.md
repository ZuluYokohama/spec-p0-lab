# Agent handoff

Supply these after the first chain finishes. The first useful output is a
validation report, not a prose verdict.

## Required

- Source-repo revision (`git rev-parse HEAD`) matching `prereg/lock.json`.
- `prereg/eval_norm.py` bytes identical to the locked executable.
- `prereg/execution_closure.json` (interpreter, deps hash, command).
- `prereg/gate_spec.json` with `g1_g3_version`, `g1_g3_pointer`, `g1_g3_hash`.
- `prereg/expected_matrix.json` listing every confirmatory arm and L.
- `prereg/g4_region_policy.json` pinning indexing, coordinates, axis,
  reduction, mask, quantile, NaN policy, layer/head reduction, L=512 branch.
- `prereg/claim_precedence.json` and `prereg/terminology_policy.json`.
- `evidence/eval_norm.jsonl` — confirmatory cells only.
- `adjudication/g1_g3.json`.
- `blind_g4/commitment.json` then `prereveal_lock.json` then `reveal.json`.

## Optional until signoff

- `adjudication/round2_verdict.json` bound by SHA-256 to the five artifacts.
- `report/FINDINGS.md` — narrative only; scanned for noun leak.

## Command

```bash
PYTHONPATH=src python -m round2_bridge validate ./round2_bundle --repo /path/to/source-repo --output validation.json
```

Do not update the SLM program until status is READY_FOR_SIGNOFF.
