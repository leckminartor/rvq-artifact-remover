"""RVQ Artifact Remover engine.

Offline deep-processing pipeline targeting neural-codec quantization
residuals (EnCodec / SoundStream / DAC style RVQ artifacts):

1. HF envelope-ripple flattener  - removes codec frame-rate AM comb
   structure (e.g. 75 Hz for EnCodec, including its 2x/3x harmonics) from
   high-band envelopes using a decimated rectify envelope.
2. Frozen-noise "unfreezer"      - detects temporally static spectral bins
   (quantization noise frozen across frames, measured with a transient-
   trimmed robust std) and attenuates them while re-injecting TPDF dither
   with independent phase to re-naturalize the noise floor.
3. Pre-echo guard                - suppresses codec window-leakage ghost
   echo in quiet frames before sharp transients.
4. Transient restoration         - re-applies percussive gain lost to
   codec smearing.
5. De-metal adaptive gate        - attenuates music-following codec noise
   (metallic sheen / thin artificial hall) via minimum-statistics noise
   estimation and smoothed Wiener-style gating; sustained tones protected.
6. Adaptive bandlimit            - gentle roll-off above the detected
   musical energy edge where RVQ noise dominates but content does not.
"""

from concurrent.futures import ThreadPoolExecutor

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


ENV_DECIM = 8


def _band_env(band, sr, decim=ENV_DECIM, cutoff=240.0):
    """Cheap AM envelope (rectify + low-pass + decimate).

    ~10x faster than a Hilbert transform at full rate; envelope detail up to
    ~240 Hz is preserved, which covers all codec frame rates (12.5-125 Hz).
    Returns the envelope and its sample rate.
    """
    fs_d = sr / float(decim)
    anti = sps.butter(2, min(fs_d * 0.45, sr * 0.45), btype="lowpass",
                      fs=sr, output="sos")
    a = sps.sosfilt(anti, np.abs(band))
    n = (len(a) // decim) * decim
    if n < decim * 2:
        return np.zeros(2), fs_d
    a_d = a[:n].reshape(-1, decim).mean(axis=1)
    lp = sps.butter(4, cutoff, btype="lowpass", fs=fs_d, output="sos")
    env = sps.sosfiltfilt(lp, a_d)
    return np.maximum(env, 0.0), fs_d


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
        env, fs_d = _band_env(b, sr)
        line = _coherent_line(env, fs_d, ripple_hz)
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
        env, fs_env = _band_env(band, sr)
        med = float(np.median(env))
        meds.append(med + EPS)
        envs.append(env - med)
    n = envs[0].size
    fs_env = sr / float(ENV_DECIM)
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


def comb_notch(x, sr, hf_start, ripple_hz, strength, cancel_check=None,
               harmonics=(1.0, 2.0, 3.0)):
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
        env, fs_d = _band_env(band, sr)
        if env.size < 8:
            out_hf += band
            continue
        g = np.ones_like(env)
        for h in harmonics:
            f_h = ripple_hz * h
            if f_h * 1.25 >= 0.45 * fs_d:
                continue
            ripple = sps.sosfiltfilt(
                sps.butter(3, [f_h * 0.8, f_h * 1.2], btype="bandpass",
                           fs=fs_d, output="sos"), env)
            g = g * (1.0 - (k / h) * (ripple / np.maximum(env, EPS)))
        g = np.clip(g, 0.25, 2.5)
        smooth_cut = min(ripple_hz * 1.5 * max(harmonics), 0.45 * fs_d)
        g = sps.sosfiltfilt(
            sps.butter(2, smooth_cut, btype="lowpass", fs=fs_d, output="sos"), g)
        g_full = np.interp(np.arange(len(band)),
                           np.arange(len(g)) * ENV_DECIM, g)
        out_hf += band * g_full
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
    flux = np.maximum(0.0, np.diff(mag_orig[hf], axis=1)).sum(axis=0)
    base = ndimage.gaussian_filter1d(flux, 16)
    trans = np.maximum(0.0, flux - base)
    ref = np.percentile(trans, 95) + EPS
    env_n = np.clip(trans / ref, 0.0, 1.0)
    gain = 1.0 + 0.25 * strength * env_n
    S2 = S.copy()
    S2[hf, 1:] *= gain[None, :]
    return S2


def echo_guard(S, mag_ref, freqs, hf_start, strength, pre_frames=5):
    """Suppress codec pre-echo (window leakage) before sharp transients.

    RVQ codecs smear sharp hits across adjacent STFT frames; the leaked
    energy in otherwise quiet frames before a hit is heard as a short
    reverse-reverb ghost. Frames preceding detected flux peaks are
    attenuated on the HF band while the hit frame itself stays untouched.
    """
    hf = freqs >= hf_start * 0.7
    if not hf.any() or S.shape[1] < 3 * pre_frames + 8:
        return S
    flux = np.maximum(0.0, np.diff(mag_ref[hf], axis=1)).sum(axis=0)
    flux = np.concatenate(([0.0], flux))
    base = ndimage.gaussian_filter1d(flux, 16)
    trans = np.maximum(0.0, flux - base)
    ref = np.percentile(trans, 95) + EPS
    env_n = np.clip(trans / ref, 0.0, 1.0)
    n = S.shape[1]
    att = np.zeros(n)
    for d in range(1, pre_frames + 1):
        a = 0.9 * strength * (1.0 - d / (pre_frames + 1.0)) * env_n
        shifted = np.zeros(n)
        shifted[:n - d] = a[d:]
        att = np.maximum(att, shifted)
    out = S.copy()
    out[hf] = S[hf] * (1.0 - np.minimum(att, 0.6))[None, :]
    return out


def demi_gate(S, freqs, sr, strength, hf_start, hop=1024, n_fft=4096,
              max_att_db=9.0):
    """Adaptive spectral gate against music-following codec noise (de-metal).

    Quantization noise that rides along with the music is not static (the
    frozen-bin unfreezer misses it) and is heard as a metallic sheen or a
    thin artificial hall. A per-bin noise power floor is estimated with
    rolling minimum statistics; Wiener-style over-subtraction with
    temporally smoothed gains attenuates the sheen, sustained tones are
    protected by the phase-lag test and treated bins are re-naturalized
    with TPDF dither at independent phase.
    """
    hf = freqs >= hf_start * 0.85
    if not hf.any() or S.shape[1] < 16:
        return S
    mag = np.abs(S)
    tone = _tone_likeness(S, hop, n_fft)
    protect = tone >= 0.5
    P = ndimage.gaussian_filter(mag[hf] ** 2, sigma=(1.0, 2.0))
    win = max(8, int(round(0.6 * sr / hop)))
    floor = ndimage.minimum_filter1d(P, size=win, axis=1, mode="nearest")
    noise = 2.0 * floor
    sub = noise / (P + EPS)
    k = 0.9 * float(np.clip(strength, 0.0, 1.0))
    att_depth = 10 ** (-(2.0 + (max_att_db - 2.0) * strength) / 20.0)
    g = np.sqrt(np.clip(1.0 - k * sub, 0.0, 1.0))
    g = np.clip(g, att_depth, 1.0)
    g = ndimage.gaussian_filter(g, sigma=(1.5, 4.0))
    g[protect[hf]] = 1.0
    m = 1.0 - g
    rng = np.random.default_rng(SEED)
    tpdf = rng.uniform(-1, 1, size=m.shape) + rng.uniform(-1, 1, size=m.shape)
    phase = rng.uniform(0.0, 2.0 * np.pi, size=m.shape)
    dith = tpdf * mag[hf] * m * 0.35 * np.exp(1j * phase)
    out = S.copy()
    out[hf] = S[hf] * g + dith
    return out


def bandlimit(S, freqs, f_edge, strength, max_db=6.0):
    f1 = max(f_edge * 1.02, 1000.0)
    floor = 10 ** (-max_db * strength / 20.0)
    mask = floor + (1.0 - floor) / (1.0 + (freqs / f1) ** 8.0)
    return S * mask[:, None]


def _energy_edge(y, sr, n_fft=4096, hop=1024):
    mono = y if y.ndim == 1 else y.mean(axis=0)
    S = np.abs(librosa.stft(mono, n_fft=n_fft, hop_length=hop, window="hann"))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    med = np.median(S, axis=1)
    cum = np.cumsum(med) / (np.sum(med) + EPS)
    idx = int(np.searchsorted(cum, 0.995))
    return float(freqs[min(idx, len(freqs) - 1)])


def _process_channel(x, sr, strength, hf_start, comb_freq, do_comb,
                     use_unfreeze, use_transient, use_echo_guard, use_demi,
                     f_edge, use_bandlimit, cancel_check, status_cb, label):
    n_fft = 4096
    hop = 1024
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    _check_cancel(cancel_check)
    if status_cb:
        status_cb(f"{label}: comb stage")
    if do_comb:
        x = comb_notch(x, sr, hf_start, comb_freq, strength, cancel_check)
    _check_cancel(cancel_check)
    if status_cb:
        status_cb(f"{label}: spectral cleanup")
    S = librosa.stft(x, n_fft=n_fft, hop_length=hop, window="hann")
    mag0 = np.abs(S)
    if use_unfreeze:
        S = unfreeze_frozen(S, freqs, strength, hf_start, hop=hop, n_fft=n_fft)
    _check_cancel(cancel_check)
    if use_echo_guard:
        S = echo_guard(S, mag0, freqs, hf_start, strength)
    if use_transient:
        S = transient_boost(S, mag0, freqs, hf_start, strength)
    if use_demi:
        S = demi_gate(S, freqs, sr, strength, hf_start, hop=hop, n_fft=n_fft)
    _check_cancel(cancel_check)
    if use_bandlimit and f_edge is not None and f_edge < 0.8 * sr / 2.0:
        S = bandlimit(S, freqs, f_edge, strength)
    return librosa.istft(S, hop_length=hop, window="hann", length=len(x))


def process(y, sr, strength=0.6, hf_start=4000.0, comb_freq=75.0,
            use_comb=True, use_unfreeze=True, use_transient=True,
            use_bandlimit=True, use_echo_guard=True, use_demi=True,
            cancel_check=None, compute_metrics=True,
            parallel_channels=True, status_cb=None, comb_score=None):
    _check_cancel(cancel_check)
    strength = float(np.clip(strength, 0.0, 1.0))
    metrics_in = None
    f_edge = None
    if compute_metrics:
        metrics_in, _ = analyze(y, sr, hf_start=hf_start, comb_freq=comb_freq)
        comb_score = metrics_in["comb_score"]
        f_edge = metrics_in["energy_edge_hz"]
    do_comb = bool(use_comb and (comb_score is None or comb_score > 0.03))
    if use_bandlimit and f_edge is None:
        f_edge = _energy_edge(y, sr)

    if status_cb:
        status_cb("DSP stages (comb, unfreeze, echo guard, transient, "
                  "de-metal, bandlimit)")

    channels = [y[c] for c in range(y.shape[0])]
    n_ch = len(channels)
    args = (sr, strength, hf_start, comb_freq, do_comb, use_unfreeze,
            use_transient, use_echo_guard, use_demi, f_edge, use_bandlimit,
            cancel_check)

    if parallel_channels and n_ch > 1 and y.shape[1] > sr // 2:
        with ThreadPoolExecutor(max_workers=min(2, n_ch)) as ex:
            outs = list(ex.map(
                lambda p: _process_channel(p[1], *args, status_cb,
                                           f"channel {p[0] + 1}/{n_ch}"),
                enumerate(channels)))
    else:
        outs = [_process_channel(ch, *args, status_cb, f"channel {i + 1}/{n_ch}")
                for i, ch in enumerate(channels)]
    out = np.stack(outs)

    _check_cancel(cancel_check)
    if status_cb:
        status_cb("finalising levels")
    rms_in = np.sqrt(np.mean(y ** 2)) + EPS
    rms_out = np.sqrt(np.mean(out ** 2)) + EPS
    out *= float(np.clip(rms_in / rms_out, 0.5, 2.0))
    peak = np.max(np.abs(out))
    if peak > 0.999:
        out *= 0.999 / peak

    rep = None
    if compute_metrics:
        metrics_out, _ = analyze(out, sr, hf_start=hf_start, comb_freq=comb_freq)
        rep = {"before": metrics_in, "after": metrics_out}
    return out, rep
