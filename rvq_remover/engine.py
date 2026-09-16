"""RVQ Artifact Remover engine.

Offline deep-processing pipeline targeting neural-codec quantization
residuals (EnCodec / SoundStream / DAC style RVQ artifacts):

1. HF envelope-ripple flattener  - removes codec frame-rate AM comb
   structure (e.g. 75 Hz for EnCodec) from high-band envelopes using a
   Hilbert-transform envelope at full time resolution.
2. Frozen-noise "unfreezer"      - detects temporally static spectral bins
   (quantization noise frozen across frames, measured with a transient-
   trimmed robust std) and attenuates them while re-injecting TPDF dither
   with independent phase to re-naturalize the noise floor.
3. Transient restoration         - re-applies percussive gain lost to
   codec smearing.
4. Adaptive bandlimit            - gentle roll-off above the detected
   musical energy edge where RVQ noise dominates but content does not.
"""

import numpy as np
import librosa
import soundfile as sf
from scipy import signal as sps
from scipy import ndimage

EPS = 1e-12
SEED = 20260916


class Cancelled(Exception):
    """Raised when the user cancels processing at a stage boundary."""


def _check_cancel(cancel_check):
    if cancel_check is not None and cancel_check():
        raise Cancelled()


def load_audio(path, sr=None):
    y, sr = librosa.load(path, sr=sr, mono=False)
    if y.ndim == 1:
        y = y[None, :]
    return np.ascontiguousarray(y.astype(np.float64)), sr


def save_audio(path, y, sr):
    data = np.clip(y.T, -1.0, 1.0).astype(np.float64)
    sf.write(path, data, sr, subtype="PCM_24")
    return path


def _band_envelope(x, sr, hf_start):
    sos = sps.butter(4, hf_start, btype="highpass", fs=sr, output="sos")
    xh = sps.sosfilt(sos, x)
    env = np.abs(sps.hilbert(xh))
    return xh, env


def _coherent_line(env, sr, f0):
    n = len(env)
    e = env - np.mean(env)
    z = np.sum(e * np.exp(-1j * 2.0 * np.pi * f0 * np.arange(n) / sr)) / n
    return 2.0 * float(np.abs(z))


def _robust_std_db(L):
    thr = np.percentile(L, 90, axis=1, keepdims=True)
    M = np.where(L <= thr, L, np.nan)
    with np.errstate(invalid="ignore"):
        std = np.nanstd(M, axis=1)
    return np.nan_to_num(std, nan=0.0)


def _tone_likeness(S, hop, n_fft):
    lag = max(1, n_fft // hop)
    ph = np.angle(S)
    d = ph[:, lag:] - ph[:, :-lag]
    d = np.angle(np.exp(1j * d))
    C = np.abs(np.mean(np.exp(1j * d), axis=1))
    return C


def _log_band_edges(hf_start, sr, n_bands=6):
    f_max = min(sr / 2.0 * 0.99, 20000.0)
    if hf_start >= f_max:
        return []
    edges = hf_start * (f_max / hf_start) ** (np.arange(n_bands + 1) / n_bands)
    return list(zip(edges[:-1], edges[1:]))


def _band_comb_depths(x, sr, hf_start, ripple_hz):
    edges = _log_band_edges(hf_start, sr)
    depths = []
    for lo, hi in edges:
        sos = sps.butter(4, [lo, hi], btype="bandpass", fs=sr, output="sos")
        b = sps.sosfilt(sos, x)
        env = np.abs(sps.hilbert(b))
        line = _coherent_line(env, sr, ripple_hz)
        depths.append(line / (float(np.median(env)) + EPS))
    return depths, edges


KNOWN_CODEC_RATES = (12.5, 25.0, 37.5, 50.0, 62.5, 75.0, 83.3, 86.1,
                     87.5, 100.0, 112.5, 125.0)


def detect_comb_freq(y, sr, hf_start=4000.0, fmin=10.0, fmax=125.0,
                     candidates=None):
    """Scan plausible codec frame rates and rank them by coherent AM depth.

    Only known/quantized codec frame rates are scanned (neural codecs use a
    fixed, by-construction quantized frame rate); this avoids confusing the
    detector with musical tempo periodicity. Ranking combines depth with
    prominence over neighboring candidates.
    """
    mono = y.mean(axis=0)
    edges = _log_band_edges(hf_start, sr)
    if not edges:
        return []
    if candidates is None:
        candidates = [f for f in KNOWN_CODEC_RATES if fmin <= f <= fmax]
    envs = []
    meds = []
    for lo, hi in edges:
        sos = sps.butter(4, [lo, hi], btype="bandpass", fs=sr, output="sos")
        band = sps.sosfilt(sos, mono)
        env = np.abs(sps.hilbert(band))
        meds.append(float(np.median(env)) + EPS)
        envs.append(env[::8] - np.median(env))
    n = envs[0].size
    fs_env = sr / 8.0
    med_max = max(meds) if meds else 0.0
    rms_floor = 1e-4 * float(np.sqrt(np.mean(mono ** 2))) + EPS
    pairs = [(med, np.fft.rfft(e)) for med, e in zip(meds, envs)
             if med > 0.01 * med_max and med > rms_floor]
    if not pairs:
        return []
    spectra = [X for _, X in pairs]
    meds_ok = [med for med, _ in pairs]
    results = []
    for f in candidates:
        idx = int(round(f * n / fs_env))
        if idx <= 0 or idx >= spectra[0].size:
            continue
        best = 0.0
        for med, X in zip(meds_ok, spectra):
            depth = 2.0 * abs(X[idx]) / n / med
            best = max(best, depth)
        results.append((float(f), float(best)))
    if not results:
        return []
    results.sort(key=lambda r: r[0])
    fs_arr = np.array([r[0] for r in results])
    d_arr = np.array([r[1] for r in results])
    proms = np.zeros_like(d_arr)
    for i, f in enumerate(fs_arr):
        w = np.abs(fs_arr - f) <= 15.0
        w[i] = False
        base = float(np.median(d_arr[w])) if w.any() else 0.0
        proms[i] = max(0.0, d_arr[i] - base)
    order = np.argsort(-proms)
    return [(float(fs_arr[i]), float(d_arr[i])) for i in order]
    results.sort(key=lambda r: -r[1])
    return results


def analyze(y, sr, n_fft=4096, hop=1024, hf_start=4000.0, comb_freq=75.0):
    mono = y.mean(axis=0)
    S_c = librosa.stft(mono, n_fft=n_fft, hop_length=hop, window="hann")
    S = np.abs(S_c)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    L = 20.0 * np.log10(S + EPS)
    std_db = _robust_std_db(L)
    mean_db = L.mean(axis=1)
    tone = _tone_likeness(S_c, hop, n_fft)
    hf = freqs >= hf_start
    frozen = hf & (std_db < 4.5) & (tone < 0.5)
    med_mag = np.median(S, axis=1)
    denom = float(np.sum(med_mag[hf] ** 2)) if hf.any() else 0.0
    frozen_pct = float(np.sum(med_mag[frozen] ** 2) / denom) if denom > 0 else 0.0

    flatness = 0.0
    if hf.any():
        P = S[hf].mean(axis=1)
        flatness = float(np.exp(np.mean(np.log(P + EPS))) / (np.mean(P) + EPS))

    depths, _ = _band_comb_depths(mono, sr, hf_start, comb_freq)
    comb_score = float(max(depths)) if depths else 0.0

    med = np.median(S, axis=1)
    cum = np.cumsum(med) / (np.sum(med) + EPS)
    edge_idx = int(np.searchsorted(cum, 0.995))
    f_edge = float(freqs[min(edge_idx, len(freqs) - 1)])

    metrics = {
        "frozen_band_pct": frozen_pct,
        "metallic_flatness": flatness,
        "comb_score": comb_score,
        "energy_edge_hz": f_edge,
        "hf_noise_floor_db": float(np.percentile(mean_db[hf], 25)) if hf.any() else -120.0,
    }
    aux = {"freqs": freqs, "std_db": std_db, "mean_db": mean_db,
           "hf_floor_db": metrics["hf_noise_floor_db"], "frozen": frozen, "hf": hf}
    return metrics, aux


def comb_notch(x, sr, hf_start, ripple_hz, strength, cancel_check=None):
    k = float(np.clip(strength, 0.0, 1.0))
    edges = _log_band_edges(hf_start, sr)
    if not edges:
        return x
    sos_hp = sps.butter(4, hf_start, btype="highpass", fs=sr, output="sos")
    xh = sps.sosfilt(sos_hp, x)
    xl = x - xh
    out_hf = np.zeros_like(xh)
    for lo, hi in edges:
        _check_cancel(cancel_check)
        sos = sps.butter(4, [lo, hi], btype="bandpass", fs=sr, output="sos")
        band = sps.sosfilt(sos, xh)
        env = np.abs(sps.hilbert(band))
        ripple = sps.sosfiltfilt(
            sps.butter(3, [ripple_hz * 0.8, ripple_hz * 1.2], btype="bandpass",
                       fs=sr, output="sos"), env)
        g = 1.0 - k * (ripple / np.maximum(env, EPS))
        g = np.clip(g, 0.25, 2.5)
        g = sps.sosfiltfilt(
            sps.butter(2, ripple_hz * 2.0, btype="lowpass", fs=sr, output="sos"), g)
        out_hf += band * g
    return xl + out_hf


def unfreeze_frozen(S, freqs, strength, hf_start, hop=1024, n_fft=4096,
                    std_thresh=4.5, max_depth_db=9.0):
    mag = np.abs(S)
    L = 20.0 * np.log10(mag + EPS)
    std_db = _robust_std_db(L)
    tone = _tone_likeness(S, hop, n_fft)
    hf = freqs >= hf_start
    if not hf.any():
        return S
    frozen = (std_db < std_thresh) & (tone < 0.5) & hf
    if not frozen.any():
        return S
    m = ndimage.gaussian_filter1d(frozen.astype(float), sigma=2.0)
    m = np.clip(m, 0.0, 1.0)[:, None]
    att = 10 ** (-strength * max_depth_db / 20.0)
    gain = 1.0 - (1.0 - att) * m
    rng = np.random.default_rng(SEED)
    tpdf = rng.uniform(-1, 1, size=mag.shape) + rng.uniform(-1, 1, size=mag.shape)
    scale = np.median(mag, axis=1, keepdims=True) * att * 0.7
    scale = scale / (np.mean(np.abs(tpdf), axis=1, keepdims=True) + EPS)
    noise_mag = tpdf * scale
    phase = rng.uniform(0.0, 2.0 * np.pi, size=mag.shape)
    noise = noise_mag * np.exp(1j * phase) * m
    return S * gain + noise


def transient_boost(S, mag_orig, freqs, hf_start, strength):
    hf = freqs >= hf_start * 0.7
    if not hf.any() or S.shape[1] < 8:
        return S
    P = librosa.decompose.hpss(mag_orig, kernel_size=31)[1]
    flux = np.maximum(0.0, np.diff(P[hf], axis=1)).sum(axis=0)
    env = ndimage.gaussian_filter1d(flux, 2)
    ref = np.percentile(env, 95) + EPS
    env_n = np.clip(env / ref, 0.0, 1.0)
    gain = 1.0 + 0.25 * strength * env_n
    S2 = S.copy()
    S2[hf, 1:] *= gain[None, :]
    return S2


def bandlimit(S, freqs, f_edge, strength, max_db=6.0):
    f1 = max(f_edge * 1.02, 1000.0)
    floor = 10 ** (-max_db * strength / 20.0)
    mask = floor + (1.0 - floor) / (1.0 + (freqs / f1) ** 8.0)
    return S * mask[:, None]


def process(y, sr, strength=0.6, hf_start=4000.0, comb_freq=75.0,
            use_comb=True, use_unfreeze=True, use_transient=True,
            use_bandlimit=True, cancel_check=None):
    _check_cancel(cancel_check)
    strength = float(np.clip(strength, 0.0, 1.0))
    metrics_in, _ = analyze(y, sr, hf_start=hf_start, comb_freq=comb_freq)
    n_fft = 4096
    hop = 1024
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    out = np.zeros_like(y)
    for c in range(y.shape[0]):
        x = y[c]
        _check_cancel(cancel_check)
        if use_comb and metrics_in["comb_score"] > 0.03:
            x = comb_notch(x, sr, hf_start, comb_freq, strength, cancel_check)
        _check_cancel(cancel_check)
        S = librosa.stft(x, n_fft=n_fft, hop_length=hop, window="hann")
        mag0 = np.abs(S)
        if use_unfreeze:
            S = unfreeze_frozen(S, freqs, strength, hf_start, hop=hop, n_fft=n_fft)
        _check_cancel(cancel_check)
        if use_transient:
            S = transient_boost(S, mag0, freqs, hf_start, strength)
        if use_bandlimit and metrics_in["energy_edge_hz"] < 0.8 * sr / 2.0:
            S = bandlimit(S, freqs, metrics_in["energy_edge_hz"], strength)
        out[c] = librosa.istft(S, hop_length=hop, window="hann", length=len(x))

    _check_cancel(cancel_check)
    rms_in = np.sqrt(np.mean(y ** 2)) + EPS
    rms_out = np.sqrt(np.mean(out ** 2)) + EPS
    out *= float(np.clip(rms_in / rms_out, 0.5, 2.0))
    peak = np.max(np.abs(out))
    if peak > 0.999:
        out *= 0.999 / peak

    metrics_out, _ = analyze(out, sr, hf_start=hf_start, comb_freq=comb_freq)
    return out, {"before": metrics_in, "after": metrics_out}
