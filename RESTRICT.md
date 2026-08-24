# RESTRICT

Date: 2026-08-24
Operator: Grok 4.5 session following Grok 4.6 lab posture (premature-sheafification, comma-residue-lab).

## In bounds
- CPU-only numpy mechanism probes.
- Synthetic tokens / random maps. No pretrained weights. No length-gen claim.
- Questions allowed:
  1. Does a hard spectral cap on W_Q, W_K bound logit scale for all T?
  2. Does a tanh clamp preserve a saturated landscape while the cap prevents it?
  3. Does a free low-rank ΔW grow ||W+ΔW||_2 while a spectral-capped ΔW does not?
  4. Are weight-cap and QK-norm the same operator on random data?

## Refused
- Calling SPEC a lever.
- Sheaf energy as a quality signal (premature-sheafification already cut that layer until a cheaper baseline loses).
- Training a transformer in this repo until P0 gates pass.
- Quoting contaminated agent leaderboards as results.
