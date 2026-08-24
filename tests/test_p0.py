import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.spec_p0 import cap_spectral, entropy, probe_logit_bound, probe_lora_growth, qk_norm, softmax, spectral_norm


def test_cap_enforced():
    rng = np.random.default_rng(1)
    W = rng.normal(size=(16, 16))
    Wc = cap_spectral(W, 0.7)
    assert spectral_norm(Wc) <= 0.7 + 1e-9


def test_softmax_rows_sum():
    z = np.ones((4, 5))
    p = softmax(z)
    np.testing.assert_allclose(p.sum(axis=-1), 1.0)


def test_qk_unit():
    rng = np.random.default_rng(2)
    q, k = rng.normal(size=(8, 4)), rng.normal(size=(8, 4))
    qn, kn = qk_norm(q, k)
    np.testing.assert_allclose(np.linalg.norm(qn, axis=-1), 1.0, atol=1e-6)
    np.testing.assert_allclose(np.linalg.norm(kn, axis=-1), 1.0, atol=1e-6)


def test_entropy_uniform():
    t = 16
    p = np.full((2, t), 1.0 / t)
    np.testing.assert_allclose(entropy(p), np.log(t), rtol=1e-6)


def test_m1_and_m4_gates():
    assert probe_logit_bound().pass_gate
    assert probe_lora_growth().pass_gate
