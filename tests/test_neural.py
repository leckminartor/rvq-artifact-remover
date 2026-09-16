"""Neural stage end-to-end test (short file, CPU or GPU).

Skipped automatically when torch/demucs are not installed.
"""

import os
import tempfile
import time

import numpy as np
import librosa
import pytest
from scipy import signal as sps

torch = pytest.importorskip("torch")
pytest.importorskip("demucs", reason="demucs not installed")

from rvq_remover.engine import analyze, load_audio, process, save_audio
from rvq_remover.neural import neural_enhance

SR = 44100
DUR = 8.0


def _make_damaged(seed=7):
    rng = np.random.default_rng(seed)
    t = np.arange(int(SR * DUR)) / SR
    y = np.zeros_like(t)
    for f, a in [(110, 0.3), (220, 0.25), (277, 0.2), (330, 0.2), (440, 0.15)]:
        y += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    y += 0.15 * np.sin(2 * np.pi * 55 * t)
    for hit in np.arange(0.5, DUR - 0.5, 1.0):
        idx = int(hit * SR)
        n = int(0.15 * SR)
        if idx + n < len(y):
            burst = rng.standard_normal(n) * np.exp(-np.arange(n) / (0.02 * SR))
            y[idx:idx + n] += 0.4 * burst

    freqs = librosa.fft_frequencies(sr=SR, n_fft=4096)
    tile_band = (freqs >= 4000) & (freqs <= 8000)
    raw = librosa.stft(rng.standard_normal(len(y)), n_fft=4096, hop_length=1024)
    S_f = np.median(np.abs(raw), axis=1, keepdims=True) * np.exp(1j * np.angle(raw))
    S_f[~tile_band, :] = 0.0
    frozen = librosa.istft(S_f, hop_length=1024, window="hann", length=len(y))
    frozen *= 0.10 / (np.max(np.abs(frozen)) + 1e-9)
    hf = sps.sosfilt(sps.butter(4, [10000, 16000], btype="bandpass", fs=SR,
                                output="sos"), rng.standard_normal(len(y)))
    comb = hf * (1.0 + 0.6 * np.sin(2 * np.pi * 75.0 * t))
    comb *= 0.10 / (np.max(np.abs(comb)) + 1e-9)

    damaged = y + frozen + comb
    damaged *= 0.9 / np.max(np.abs(damaged))
    return damaged


def test_neural_pipeline():
    damaged = _make_damaged()
    tmp = tempfile.mkdtemp()
    save_audio(os.path.join(tmp, "damaged.wav"), damaged[None, :], SR)
    y_in, sr = load_audio(os.path.join(tmp, "damaged.wav"))
    m0, _ = analyze(y_in, sr)

    t0 = time.time()
    y_dsp, _ = process(y_in, sr, strength=0.8)
    m1, _ = analyze(y_dsp, sr)
    print("DSP   %.1fs: comb %.3f->%.3f  frozen %.3f->%.3f"
          % (time.time() - t0, m0["comb_score"], m1["comb_score"],
             m0["frozen_band_pct"], m1["frozen_band_pct"]))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    y_nn = neural_enhance(y_dsp, sr, strength=0.8, model_name="htdemucs",
                          status_cb=lambda m: print("  [neural]", m))
    m2, _ = analyze(y_nn, sr)
    print("NEURAL (%s) %.1fs: comb %.3f  frozen %.3f"
          % (device, time.time() - t0, m2["comb_score"], m2["frozen_band_pct"]))

    assert y_nn.shape == y_in.shape
    assert np.all(np.isfinite(y_nn))
    assert np.max(np.abs(y_nn)) <= 1.0
    assert m2["comb_score"] < m0["comb_score"], "comb did not improve end-to-end"
    assert m2["frozen_band_pct"] < m0["frozen_band_pct"], "frozen did not improve end-to-end"
    save_audio(os.path.join(tmp, "cleaned.wav"), y_nn, sr)
    print("PASS: DSP-only comb %.3f frozen %.3f | +neural comb %.3f frozen %.3f"
          % (m1["comb_score"], m1["frozen_band_pct"], m2["comb_score"], m2["frozen_band_pct"]))
