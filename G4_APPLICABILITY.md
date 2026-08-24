# G4 applicability branch (locked before unblind)

This file is the applicability declaration the eval bridge must already
have seen. If a results bundle does not cite this branch (or an identical
paragraph in the prereg), the bundle is **REJECTED**. No post-hoc rule.

## Indexing

- Sequence length `L` counts tokens.
- Query positions are **0-indexed** in the half-open interval `[0, L)`.
- There is no position `L`. Position `512` exists only when `L > 512`.

## Eligible sets (normative)

G4-p99 eligible set:

    E_p99(L) = { q in [0, L) | q >= 512 }

G4-entropy eligible set:

    E_H(L) = { q in [0, L) | q >= L-512 }

These are different sets. They must be written as different rows.
They must not be averaged. They must not be renamed "the tail."

## Cardinality on the locked grid

| L    | |E_p99| | |E_H| | note |
|------|---------|-------|------|
| 512  | **0**   | 512   | p99 set empty; entropy set is the whole sequence |
| 1024 | 512     | 512   | p99 = [512, 1024); H = [512, 1024); **same 512 positions** |
| 2048 | 1536    | 512   | differ by 1024 |
| 4096 | 3584    | 512   | differ by 3072 |

At L=1024 the two statistics happen to share the same positions. That is
an accident of the grid, not a license to treat them as one probe at
L=2048 or L=4096.

## Applicability branch (no invention after results)

IF |E_p99(L)| == 0:
    G4-p99(L) := NA
    The cell is written as the token `NA`.
    FORBIDDEN after seeing numbers:
      - drop the row
      - drop NaNs and average the rest
      - substitute E_H(L)
      - substitute last-512
      - shift the cutoff from 512 to 256 / 0 / L//2
      - switch to 1-based indexing so position 512 exists
    The first length on the locked grid at which G4-p99 is applicable
    is L=1024.

IF |E_H(L)| == 0:
    G4-entropy(L) := NA
    (Does not occur on this grid under the declared indexing.)

IF a bundle reports a finite G4-p99 at L=512:
    REJECT the bundle. That number cannot be produced by E_p99(512).

IF a bundle reports G4-p99 at L=512 as a copy of G4-entropy or of
any tail-512 slice:
    REJECT the bundle.

## What the prereg must contain

A results bundle is admissible only if the preregistration (or this file,
hashed and cited by the prereg) already contains:

1. The 0-index / `[0, L)` convention.
2. The two set definitions above, verbatim in meaning.
3. The empty-set → `NA` branch for G4-p99 at L=512.
4. An explicit ban on tail-512 substitution and NaN-dropping.

Missing any of 1–4: reject. Do not patch the prereg after unblind.
