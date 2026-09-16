"""Neural restoration stage: Demucs separation + per-stem RVQ cleanup.

htdemucs re-synthesizes each stem through a network trained on clean studio
recordings. Codec residual noise that belongs to no instrument largely
disappears when stems are recombined; per-stem targeted DSP cleanup then
removes what remains with less collateral damage than mix-level processing.
"""

import os

import numpy as np

from . import engine

TARGET_SR = 44100

STEM_CFG = {
    "drums":  dict(hf_start_scale=1.0, transient=True,  unfreeze=True,  comb=True,  bandlimit=True),
    "vocals": dict(hf_start_scale=1.0, transient=False, unfreeze=True,  comb=True,  bandlimit=True),
    "bass":   dict(hf_start_scale=1.5, transient=False, unfreeze=True,  comb=False, bandlimit=True),
    "other":  dict(hf_start_scale=1.0, transient=True,  unfreeze=True,  comb=True,  bandlimit=True),
}


def _match_length(y, n_target):
    n = y.shape[1]
    if n == n_target:
        return y
    if n > n_target:
        return y[:, :n_target]
    return np.pad(y, ((0, 0), (0, n_target - n)))


def _resample(y, sr_in, sr_out):
    if sr_in == sr_out:
        return y
    import librosa
    out = np.stack([librosa.resample(c, orig_sr=sr_in, target_sr=sr_out)
                    for c in y])
    return out


def _separate(y, sr, model_name, device):
    import torch
    from demucs.apply import apply_model
    from demucs import pretrained

    torch.set_num_threads(max(1, os.cpu_count() or 1))
    model = pretrained.get_model(model_name)
    model.to(device).eval()
    model_sr = model.samplerate

    y44 = _resample(y, sr, model_sr)
    mono = y44.shape[0] == 1
    if mono:
        y44 = np.repeat(y44, 2, axis=0)

    wav = torch.from_numpy(np.ascontiguousarray(y44.astype(np.float32)))[None]
    with torch.no_grad():
        src = apply_model(model, wav, device=device, shifts=0,
                          overlap=0.25, split=True, progress=False)[0]
    src = src.cpu().numpy()

    n_orig = y.shape[1]
    stems = {}
    for i, name in enumerate(model.sources):
        st = src[i]
        if mono:
            st = st.mean(axis=0, keepdims=True)
        stems[name] = _match_length(
            _resample(st.astype(np.float64), model_sr, sr), n_orig)
    return stems


def neural_enhance(y, sr, strength=0.6, hf_start=4000.0, comb_freq=75.0,
                   model_name="htdemucs", device=None, use_transient=None,
                   stem_strength=0.8, use_comb=True, use_bandlimit=True,
                   status_cb=None, cancel_check=None):
    engine._check_cancel(cancel_check)
    if device is None:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if status_cb:
        status_cb(f"Separating stems with {model_name} on {device} "
                  f"(first run downloads the model)...")
    stems = _separate(y, sr, model_name, device)
    engine._check_cancel(cancel_check)

    out = np.zeros_like(y)
    for name, st in stems.items():
        engine._check_cancel(cancel_check)
        cfg = STEM_CFG.get(name, STEM_CFG["other"])
        if status_cb:
            status_cb(f"Cleaning stem: {name}...")
        hfs = hf_start * cfg["hf_start_scale"]
        cleaned, _ = engine.process(
            st, sr,
            strength=float(np.clip(strength * stem_strength, 0.0, 1.0)),
            hf_start=hfs, comb_freq=comb_freq,
            use_comb=use_comb and cfg["comb"],
            use_unfreeze=cfg["unfreeze"],
            use_transient=cfg["transient"] if use_transient is None else use_transient,
            use_bandlimit=use_bandlimit and cfg["bandlimit"],
            cancel_check=cancel_check,
        )
        out += cleaned

    out = out[:, :y.shape[1]]
    rms_in = np.sqrt(np.mean(y ** 2)) + engine.EPS
    rms_out = np.sqrt(np.mean(out ** 2)) + engine.EPS
    out *= float(np.clip(rms_in / rms_out, 0.5, 2.0))
    peak = np.max(np.abs(out))
    if peak > 0.999:
        out *= 0.999 / peak
    return out
