# spec-p0-lab

CPU-only mechanism lab for **SPEC** (hard spectral cap on attention maps) versus clamp, QK-norm, σReparam-style scale, and LoRA spectral growth.

This is **not** a length-generalization result. It is P0 from the 2026-08-24 operational pipeline: the gates that must pass before any GPU hour is spent on P1.

## Lineage

| Artifact | What it actually did |
|---|---|
| Grok 4.6 × `premature-sheafification` (2026-08-12) | Built a null-calibrated zeta→geometry→sheaf pipeline and **cut the sheaf layer**. Connection heat lost to a 1-D distance quantile. Geometry was decorative. |
| Grok 4.6 × attached SPEC / operator-norm audits | Literature cell is empty. QK-norm arm mandatory. Adapter×length is open. |
| This repo (this session, 2026-08-24) | Executable synthetic probes for mechanism clauses M1–M4. Same posture: restrict, measure, keep negatives, refuse the product sentence. |

If P2 energy-vs-cosine is ever run, `premature-sheafification` is the prior that says **start from the cheap baseline**. Do not re-sheafify first.

## Run

```bash
python -m src.spec_p0
python -m pytest tests -q
```

Writes `results/p0_synthetic.json`.

## Gates

| Probe | Pass means |
|---|---|
| M1 logit bound | Cap enforces σ(W)≤c and FREE OOD logits explode harder than SPEC |
| M1b clamp vs bound | tanh hits the box; bound reduces scale without saturation |
| M2 entropy vs T | SPEC entropy/log T ≥ FREE (sits on the *dispersion* axis — a warning, not a win) |
| M3 weight vs activation | SPEC logits and QK-norm logits are not the same map (cosine < 0.99) |
| M4 LoRA growth | Free low-rank steps grow σ(W); capped ΔW grows less |

M2 passing is a **yellow flag for the paper**, not a celebration. The log-n literature says shrinking logits flattens softmax as T grows. P1 exists to see whether a real model is in the saturation regime instead.

## Refused claims

- "lever"
- length extrapolation
- sheaf energy as a verifier
- anything measured only on these Gaussians transferring to Gemma/Qwen
