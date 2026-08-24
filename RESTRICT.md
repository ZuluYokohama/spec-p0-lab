# RESTRICT

Date: 2026-08-24
Operator: Grok 4.5 session following Grok 4.6 lab posture (premature-sheafification, comma-residue-lab).

## In bounds
- CPU-only numpy / torch mechanism probes.
- Synthetic tokens / random maps. No pretrained weights. No length-gen claim.
- G4 applicability lock (see G4_APPLICABILITY.md, prereg/g4_applicability.json).
- Questions allowed:
  1. Does a hard spectral cap on W_Q, W_K bound logit scale for all T?
  2. Does a tanh clamp preserve a saturated landscape while the cap prevents it?
  3. Does a free low-rank ΔW grow ||W+ΔW||_2 while a spectral-capped ΔW does not?
  4. Are weight-cap and QK-norm the same operator on random data?
  5. Does the eval bridge reject a finite G4-p99 at L=512 under 0-index [0, L)?

## Refused
- Calling SPEC a lever.
- Noun "constrained mixers" in FINDINGS, captions, or cited records until G3 licenses it.
- Sheaf energy as a quality signal (premature-sheafification already cut that layer until a cheaper baseline loses).
- Training a transformer in this repo until P0 gates pass.
- Quoting contaminated agent leaderboards as results.
- After unblind: drop NaN, impute, substitute tail-512, reindex 1-based, or move the 512 cutoff to rescue G4-p99 at L=512.
