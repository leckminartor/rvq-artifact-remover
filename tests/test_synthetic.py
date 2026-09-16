"""Synthetic RVQ-damage verification test.

Damage model:
- Frozen quantization-noise tiles in 4-8 kHz (static spectral envelope with
  natural phase evolution).
- Frame-rate (75 Hz) amplitude modulation of HF noise in 10-16 kHz.
"""

import tempfile
import os

import numpy as np
import librosa
from scipy import signal as sps

from rvq_remover.engine import analyze, load_audio, process, save_audio

SR = 44100
DUR = 20.0


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

    n_fft, hop = 4096, 1024
    freqs = librosa.fft_frequencies(sr=SR, n_fft=n_fft)
    tile_band = (freqs >= 4000) & (freqs <= 8000)

    raw = librosa.stft(rng.standard_normal(len(y)), n_fft=n_fft, hop_length=hop)
    static_mag = np.median(np.abs(raw), axis=1, keepdims=True)
    S_f = static_mag * np.exp(1j * np.angle(raw))
    S_f[~tile_band, :] = 0.0
    frozen_noise = librosa.istft(S_f, hop_length=hop, window="hann", length=len(y))
    frozen_noise *= 0.10 / (np.max(np.abs(frozen_noise)) + 1e-9)

    hf_noise = rng.standard_normal(len(y))
    hf_noise = sps.sosfilt(sps.butter(4, [10000, 16000], btype="bandpass", fs=SR,
                                      output="sos"), hf_noise)
    am = 1.0 + 0.6 * np.sin(2 * np.pi * 75.0 * t)
    comb_noise = hf_noise * am
    comb_noise *= 0.10 / (np.max(np.abs(comb_noise)) + 1e-9)

    damaged = y + frozen_noise + comb_noise
    damaged *= 0.9 / np.max(np.abs(damaged))
    return damaged


def test_synthetic_pipeline():
    damaged = _make_damaged()
    tmp = tempfile.mkdtemp()
    in_path = os.path.join(tmp, "damaged.wav")
    save_audio(in_path, damaged[None, :], SR)
    y_in, sr = load_audio(in_path)

    m0, _ = analyze(y_in, sr)
    y_out, rep = process(y_in, sr, strength=0.8)
    m1 = rep["after"]

    assert y_out.shape == y_in.shape
    assert np.all(np.isfinite(y_out))
    assert np.max(np.abs(y_out)) <= 1.0
    assert m1["comb_score"] < m0["comb_score"], "comb periodicity did not drop"
    assert m1["frozen_band_pct"] < m0["frozen_band_pct"], "frozen bins did not drop"
    rms_in = np.sqrt(np.mean(y_in ** 2))
    rms_out = np.sqrt(np.mean(y_out ** 2))
    assert 0.5 < rms_out / rms_in < 2.0, "loudness drifted"

    print("PASS: comb %0.3f->%0.3f  frozen %0.3f->%0.3f"
          % (m0["comb_score"], m1["comb_score"],
             m0["frozen_band_pct"], m1["frozen_band_pct"]))


def test_detect_comb_freq():
    from rvq_remover.engine import detect_comb_freq

    damaged = _make_damaged(seed=9)
    det = detect_comb_freq(damaged[None, :], SR)
    assert det, "no frame-rate candidates detected"
    top_freq, top_depth = det[0]
    assert abs(top_freq - 75.0) <= 2.6, f"detected {top_freq} Hz instead of 75 Hz"
    assert top_depth > 0.05, f"comb depth too low: {top_depth}"
