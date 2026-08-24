"""P0 mechanism lab. Numpy only. No length-gen claim.

Run: python -m src.spec_p0
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

RNG = np.random.default_rng(0)


def spectral_norm(W: np.ndarray) -> float:
    return float(np.linalg.svd(W, compute_uv=False)[0])


def cap_spectral(W: np.ndarray, c: float) -> np.ndarray:
    s = spectral_norm(W)
    if s <= c:
        return W.copy()
    return W * (c / s)


def softmax(logits: np.ndarray, axis: int = -1) -> np.ndarray:
    z = logits - logits.max(axis=axis, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=axis, keepdims=True)


def entropy(p: np.ndarray, axis: int = -1) -> np.ndarray:
    p = np.clip(p, 1e-12, 1.0)
    return -(p * np.log(p)).sum(axis=axis)


def tanh_cap(logits: np.ndarray, soft_cap: float = 50.0) -> np.ndarray:
    return soft_cap * np.tanh(logits / soft_cap)


def qk_norm(q: np.ndarray, k: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    qn = q / (np.linalg.norm(q, axis=-1, keepdims=True) + 1e-12)
    kn = k / (np.linalg.norm(k, axis=-1, keepdims=True) + 1e-12)
    return qn, kn


@dataclass
class ProbeResult:
    name: str
    numbers: dict
    pass_gate: bool
    note: str


def probe_logit_bound(d: int = 32, t: int = 256, c: float = 1.0) -> ProbeResult:
    """M1: hard cap on W_Q, W_K bounds ||Z||_2 independent of T growth in X scale."""
    X = RNG.normal(0, 1, size=(t, d))
    Wq = RNG.normal(0, 1, size=(d, d))
    Wk = RNG.normal(0, 1, size=(d, d))
    free_z = (X @ Wq) @ (X @ Wk).T / np.sqrt(d)
    spec_z = (X @ cap_spectral(Wq, c)) @ (X @ cap_spectral(Wk, c)).T / np.sqrt(d)
    # scale inputs as a cheap OOD proxy (positions with larger activation norm)
    X_ood = X * 3.0
    free_ood = (X_ood @ Wq) @ (X_ood @ Wk).T / np.sqrt(d)
    spec_ood = (X_ood @ cap_spectral(Wq, c)) @ (X_ood @ cap_spectral(Wk, c)).T / np.sqrt(d)
    nums = {
        "free_max_abs": float(np.max(np.abs(free_z))),
        "spec_max_abs": float(np.max(np.abs(spec_z))),
        "free_ood_max_abs": float(np.max(np.abs(free_ood))),
        "spec_ood_max_abs": float(np.max(np.abs(spec_ood))),
        "sigma_Wq_free": spectral_norm(Wq),
        "sigma_Wq_spec": spectral_norm(cap_spectral(Wq, c)),
        "cap": c,
        "T": t,
    }
    # gate: SPEC OOD max logit must stay below FREE OOD and not explode vs in-dist SPEC
    ok = nums["spec_ood_max_abs"] < nums["free_ood_max_abs"] and nums["sigma_Wq_spec"] <= c + 1e-9
    return ProbeResult("M1_logit_bound", nums, ok, "cap bounds map; OOD activation scale still explodes FREE")


def probe_clamp_vs_bound(d: int = 32, t: int = 256, c: float = 1.0, soft: float = 8.0) -> ProbeResult:
    """M1b: tanh clamp saturates ranking; bound keeps ordered logits."""
    X = RNG.normal(0, 1, size=(t, d))
    Wq = RNG.normal(0, 2.5, size=(d, d))  # deliberately hot
    Wk = RNG.normal(0, 2.5, size=(d, d))
    free = (X @ Wq) @ (X @ Wk).T / np.sqrt(d)
    clamped = tanh_cap(free, soft)
    bounded = (X @ cap_spectral(Wq, c)) @ (X @ cap_spectral(Wk, c)).T / np.sqrt(d)
    # ranking fidelity: correlation of row-wise ranks vs FREE
    def rank_corr(a, b) -> float:
        rs = []
        for i in range(min(32, a.shape[0])):
            ra = np.argsort(np.argsort(a[i]))
            rb = np.argsort(np.argsort(b[i]))
            rs.append(float(np.corrcoef(ra, rb)[0, 1]))
        return float(np.nanmean(rs))

    nums = {
        "free_max": float(np.max(np.abs(free))),
        "clamp_max": float(np.max(np.abs(clamped))),
        "bound_max": float(np.max(np.abs(bounded))),
        "clamp_rank_corr_vs_free": rank_corr(clamped, free),
        "bound_rank_corr_vs_free": rank_corr(bounded, free),
        "free_entropy_mean": float(entropy(softmax(free)).mean()),
        "clamp_entropy_mean": float(entropy(softmax(clamped)).mean()),
        "bound_entropy_mean": float(entropy(softmax(bounded)).mean()),
        "uniform_entropy": float(np.log(t)),
    }
    # not a pass/fail on which entropy is 'better'; gate is: clamp hits the box, bound does not sit at +/-soft
    ok = nums["clamp_max"] <= soft + 1e-6 and nums["bound_max"] < nums["free_max"]
    return ProbeResult("M1b_clamp_vs_bound", nums, ok, "clamp saturates to box; bound reduces scale without tanh saturation")


def probe_entropy_vs_T(d: int = 16, c: float = 1.0) -> ProbeResult:
    """M2: entropy vs T under FREE / SPEC / QK-norm. Dispersion axis check."""
    lengths = [32, 64, 128, 256, 512]
    rows = []
    Wq = RNG.normal(0, 1.5, size=(d, d))
    Wk = RNG.normal(0, 1.5, size=(d, d))
    Wq_c = cap_spectral(Wq, c)
    Wk_c = cap_spectral(Wk, c)
    for t in lengths:
        X = RNG.normal(0, 1, size=(t, d))
        q, k = X @ Wq, X @ Wk
        z_free = q @ k.T / np.sqrt(d)
        z_spec = (X @ Wq_c) @ (X @ Wk_c).T / np.sqrt(d)
        qn, kn = qk_norm(q, k)
        z_qk = qn @ kn.T * 1.0  # learned scale frozen to 1
        rows.append(
            {
                "T": t,
                "H_free": float(entropy(softmax(z_free)).mean()),
                "H_spec": float(entropy(softmax(z_spec)).mean()),
                "H_qk": float(entropy(softmax(z_qk)).mean()),
                "H_uniform": float(np.log(t)),
                "max_free": float(np.max(np.abs(z_free))),
                "max_spec": float(np.max(np.abs(z_spec))),
                "max_qk": float(np.max(np.abs(z_qk))),
            }
        )
    # H/log T closer to 1 => more uniform. SPEC shrinking logits should raise H toward uniform.
    frac = [
        {
            "T": r["T"],
            "free_frac": r["H_free"] / r["H_uniform"],
            "spec_frac": r["H_spec"] / r["H_uniform"],
            "qk_frac": r["H_qk"] / r["H_uniform"],
        }
        for r in rows
    ]
    spec_more_uniform = all(f["spec_frac"] >= f["free_frac"] - 1e-6 for f in frac)
    return ProbeResult(
        "M2_entropy_vs_T",
        {"rows": rows, "frac_of_uniform": frac},
        spec_more_uniform,
        "If SPEC frac_of_uniform > FREE, intervention sits on the dispersion axis (log-n literature). Not a length-gen win by itself.",
    )


def probe_lora_growth(d: int = 64, r: int = 8, steps: int = 40, cap: float = 0.5) -> ProbeResult:
    """M4: free LoRA-like ΔW grows spectral norm; capped ΔW does not."""
    W = RNG.normal(0, 0.05, size=(d, d))
    W0 = spectral_norm(W)

    def lora_step(W, capped: bool):
        A = RNG.normal(0, 0.1, size=(r, d))
        B = RNG.normal(0, 0.1, size=(d, r))
        dW = B @ A
        if capped:
            s = spectral_norm(dW)
            if s > cap:
                dW = dW * (cap / s)
        return W + dW

    W_free, W_cap = W.copy(), W.copy()
    free_track, cap_track = [W0], [W0]
    for _ in range(steps):
        W_free = lora_step(W_free, False)
        W_cap = lora_step(W_cap, True)
        free_track.append(spectral_norm(W_free))
        cap_track.append(spectral_norm(W_cap))
    nums = {
        "sigma0": W0,
        "sigma_free_end": free_track[-1],
        "sigma_cap_end": cap_track[-1],
        "free_growth": free_track[-1] / (W0 + 1e-12),
        "cap_growth": cap_track[-1] / (W0 + 1e-12),
        "delta_cap": cap,
        "free_track": free_track,
        "cap_track": cap_track,
    }
    ok = nums["sigma_free_end"] > nums["sigma_cap_end"]
    return ProbeResult("M4_lora_growth", nums, ok, "synthetic LoRA steps; not Shuttleworth intruders on a real model")


def probe_weight_vs_activation(d: int = 32, t: int = 128, c: float = 1.0) -> ProbeResult:
    """M3: QK-norm and SPEC are not the same map on random data."""
    X = RNG.normal(0, 1, size=(t, d))
    Wq = RNG.normal(0, 1.2, size=(d, d))
    Wk = RNG.normal(0, 1.2, size=(d, d))
    z_spec = (X @ cap_spectral(Wq, c)) @ (X @ cap_spectral(Wk, c)).T / np.sqrt(d)
    qn, kn = qk_norm(X @ Wq, X @ Wk)
    z_qk = qn @ kn.T
    # cosine of flattened logits; low => different landscapes
    a = z_spec.ravel()
    b = z_qk.ravel()
    cos = float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12))
    nums = {
        "logit_cosine_spec_vs_qk": cos,
        "spec_max": float(np.max(np.abs(z_spec))),
        "qk_max": float(np.max(np.abs(z_qk))),
        "spec_entropy": float(entropy(softmax(z_spec)).mean()),
        "qk_entropy": float(entropy(softmax(z_qk)).mean()),
    }
    # dissociated if cosine is not ~1
    ok = abs(cos) < 0.99
    return ProbeResult("M3_weight_vs_activation", nums, ok, "random-data dissociation only; real models may still collapse them")


def main() -> None:
    probes = [
        probe_logit_bound(),
        probe_clamp_vs_bound(),
        probe_entropy_vs_T(),
        probe_lora_growth(),
        probe_weight_vs_activation(),
    ]
    out = {
        "seed": 0,
        "claim_level": "mechanism-on-synthetic; not length-gen",
        "probes": [{"name": p.name, "pass_gate": p.pass_gate, "note": p.note, "numbers": p.numbers} for p in probes],
        "all_gates": all(p.pass_gate for p in probes),
    }
    dest = Path("results")
    dest.mkdir(exist_ok=True)
    path = dest / "p0_synthetic.json"
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("claim_level", "all_gates")}, indent=2))
    for p in probes:
        print(f"{p.name:28s} gate={'PASS' if p.pass_gate else 'FAIL'}  {p.note}")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
