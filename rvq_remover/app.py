"""RVQ Artifact Remover - Gradio desktop app."""

import os
import tempfile
import threading
import time

import gradio as gr
import librosa.display
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import __version__
from .engine import analyze, detect_comb_freq, load_audio, process, save_audio

OUT_DIR = os.path.join(os.getcwd(), "output")
os.makedirs(OUT_DIR, exist_ok=True)

_RUN = {"cancel": False}
_HISTORY = []

TITLE = "RVQ Artifact Remover"
AUTHOR = "Klaus Perner (DJ LECK)"
GITHUB_URL = "https://github.com/leckminartor/rvq-artifact-remover"
DONATE_URL = "https://paypal.me/klausminator"
SUBTITLE = (
    "Offline deep-processing for neural-codec quantization residuals "
    "(EnCodec / SoundStream / DAC). Cancels codec frame-rate comb modulation, "
    "unfreezes static quantization-noise bins, restores transients and tames "
    "the artificial air band."
)


def _neural_device_line():
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            return f"GPU neural stage: **CUDA - {name}**"
        return "Neural stage device: **CPU** (torch without CUDA - DSP stages unaffected)"
    except Exception:
        return "Neural stage device: **CPU** (torch not installed)"


def _spectrogram_ax(ax, y_mono, sr, title):
    S = np.abs(librosa.stft(y_mono, n_fft=4096, hop_length=1024))
    Sdb = librosa.amplitude_to_db(S, ref=np.max)
    librosa.display.specshow(Sdb, sr=sr, hop_length=1024,
                             x_axis="time", y_axis="hz", ax=ax, cmap="magma")
    ax.set_title(title)
    ax.set_ylim(0, min(sr // 2, 20000))


def run_analysis(path, hf_start):
    comb_update = gr.update()
    if not path:
        return None, "Upload an audio file first.", comb_update
    y, sr = load_audio(path)
    metrics, aux = analyze(y, sr, hf_start=float(hf_start))
    mono = y.mean(axis=0)

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    _spectrogram_ax(axes[0], mono, sr, "Spectrogram (original)")
    S = np.abs(librosa.stft(mono, n_fft=4096, hop_length=1024))
    Sdb = librosa.amplitude_to_db(S, ref=np.max)
    ax2 = axes[1]
    librosa.display.specshow(Sdb, sr=sr, hop_length=1024,
                             x_axis="time", y_axis="hz", ax=ax2, cmap="magma")
    overlay = np.repeat(aux["frozen"].astype(float)[:, None], Sdb.shape[1], axis=1)
    ax2.contourf(np.linspace(0, len(mono) / sr, Sdb.shape[1]), aux["freqs"],
                 np.ma.masked_less(overlay, 0.5), levels=[0.5, 1.5],
                 colors=["#00e5ff"], alpha=0.35)
    ax2.set_title("Detected frozen quantization-noise bins (cyan)")
    ax2.set_ylim(0, min(sr // 2, 20000))
    fig.tight_layout()

    report = (
        f"Frozen noise energy share (HF): {metrics['frozen_band_pct']*100:.1f}%\n"
        f"Metallic flatness score (HF):   {metrics['metallic_flatness']:.3f}\n"
        f"Codec comb depth @75 Hz:        {metrics['comb_score']:.3f}\n"
        f"Musical energy edge:            {metrics['energy_edge_hz']:.0f} Hz\n"
        f"HF noise floor:                 {metrics['hf_noise_floor_db']:.1f} dB"
    )
    det = detect_comb_freq(y, sr, hf_start=float(hf_start))
    if det:
        top = ", ".join(f"{f:.1f} Hz (depth {d:.3f})" for f, d in det[:3])
        report += (
            "\n\nDetected codec frame rate candidates:\n  " + top
        )
        top_f, top_d = det[0]
        if top_d >= 0.05:
            comb_update = gr.update(value=float(top_f))
            report += (
                f"\n'Codec frame rate' automatically set to {top_f:.1f} Hz."
            )
        else:
            report += (
                "\nNo clear codec comb found - 'Codec frame rate' left "
                "unchanged. Consider disabling the comb stage."
            )
    return fig, report, comb_update


def _mode_suffix(use_comb, use_unfreeze, use_echo_guard, use_transient,
                 use_demi, use_bandlimit, neural_on, model_name):
    letters = ""
    if use_comb:
        letters += "c"
    if use_unfreeze:
        letters += "u"
    if use_echo_guard:
        letters += "e"
    if use_transient:
        letters += "t"
    if use_demi:
        letters += "d"
    if use_bandlimit:
        letters += "b"
    if neural_on:
        letters += "-ai" + ("-ft" if model_name == "htdemucs_ft" else "")
    return letters or "none"


def run_processing(path, strength, hf_start, comb_freq, neural_on, model_name,
                   residual_pct, use_comb, use_unfreeze, use_transient,
                   use_bandlimit, use_echo_guard, use_demi):
    history_text = "\n".join(_HISTORY)
    buttons_off = (gr.update(interactive=False), gr.update(interactive=False),
                   gr.update(interactive=True))
    buttons_on = (gr.update(interactive=True), gr.update(interactive=True),
                  gr.update(interactive=False))
    if not path:
        yield None, None, "Upload an audio file first.", history_text, *buttons_on
        return
    _RUN["cancel"] = False
    yield None, None, "Loading audio...", history_text, *buttons_off
    y, sr = load_audio(path)
    yield None, None, ("Running DSP stages (comb, unfreeze, echo guard, "
                       "transient, de-metal, bandlimit)..."), history_text, *buttons_off

    holder = {"status": "", "done": False, "error": None, "y": None, "rep": None}

    def worker():
        try:
            y_out, rep = process(
                y, sr,
                strength=float(strength) / 100.0,
                hf_start=float(hf_start),
                comb_freq=float(comb_freq),
                use_comb=bool(use_comb),
                use_unfreeze=bool(use_unfreeze),
                use_transient=bool(use_transient),
                use_bandlimit=bool(use_bandlimit),
                use_echo_guard=bool(use_echo_guard),
                use_demi=bool(use_demi),
                cancel_check=lambda: _RUN["cancel"],
                status_cb=lambda m: holder.update(status="DSP - " + m),
            )
            holder["rep"] = rep
            if neural_on:
                from . import neural
                holder["y"] = neural.neural_enhance(
                    y_out, sr,
                    strength=float(strength) / 100.0,
                    hf_start=float(hf_start),
                    comb_freq=float(comb_freq),
                    model_name=model_name,
                    residual_keep=float(residual_pct) / 100.0,
                    status_cb=lambda m: holder.update(status="AI - " + m),
                    cancel_check=lambda: _RUN["cancel"],
                    comb_score=rep["before"]["comb_score"],
                )
            else:
                holder["y"] = y_out
        except Exception as exc:
            holder["error"] = exc
        finally:
            holder["done"] = True

    thread = threading.Thread(target=worker)
    thread.start()
    while not holder["done"]:
        if _RUN["cancel"]:
            yield None, None, "Cancelling - waiting for the current stage to finish...", history_text, *buttons_off
        else:
            yield None, None, holder["status"] or "Processing...", history_text, *buttons_off
        time.sleep(0.5)
    thread.join()

    from .engine import Cancelled
    if holder["error"] is not None:
        if isinstance(holder["error"], Cancelled):
            yield None, None, "Processing cancelled by user.", history_text, *buttons_on
            return
        yield None, None, f"Error: {holder['error']}", history_text, *buttons_on
        return
    y_out = holder["y"]

    base = os.path.splitext(os.path.basename(path))[0]
    safe_base = "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in base)
    suffix = _mode_suffix(bool(use_comb), bool(use_unfreeze),
                          bool(use_echo_guard), bool(use_transient),
                          bool(use_demi), bool(use_bandlimit),
                          bool(neural_on), model_name)
    out_path = os.path.join(tempfile.mkdtemp(dir=OUT_DIR),
                            f"{safe_base}_{suffix}_derq.wav")
    save_audio(out_path, y_out, sr)

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    _spectrogram_ax(axes[0], y.mean(axis=0), sr, "Before")
    _spectrogram_ax(axes[1], y_out.mean(axis=0), sr, "After (RVQ cleaned)")
    fig.tight_layout()

    if neural_on:
        rep_final, _ = analyze(y_out, sr, hf_start=float(hf_start),
                               comb_freq=float(comb_freq))
    else:
        rep_final = holder["rep"]["after"]
    b, a = holder["rep"]["before"], rep_final
    neural_note = f" (incl. AI stage: {model_name})" if neural_on else ""
    report = (
        "Metric                        Before    After\n"
        f"Frozen noise energy (HF):   {b['frozen_band_pct']*100:8.1f}%  {a['frozen_band_pct']*100:8.1f}%\n"
        f"Metallic flatness:          {b['metallic_flatness']:8.3f}  {a['metallic_flatness']:8.3f}\n"
        f"Comb depth @75 Hz:          {b['comb_score']:8.3f}  {a['comb_score']:8.3f}\n"
        f"Energy edge:          {b['energy_edge_hz']:8.0f}Hz {a['energy_edge_hz']:8.0f}Hz"
        f"\n\nPipeline: DSP stages{neural_note}"
        f"\nOutput: {os.path.basename(out_path)}"
    )

    stamp = time.strftime("%H:%M")
    desc = f"strength {float(strength):.0f}%"
    if neural_on:
        desc += f" | AI {model_name} | residual {float(residual_pct):.0f}%"
    _HISTORY.insert(0, f"[{stamp}]  {os.path.basename(out_path)}  |  {desc}")
    del _HISTORY[12:]
    history_text = "\n".join(_HISTORY)
    yield out_path, fig, report, history_text, *buttons_on


def cancel_run():
    _RUN["cancel"] = True
    return "Cancelling - waiting for the current stage to finish..."


def build():
    with gr.Blocks(title=f"{TITLE} v{__version__}") as demo:
        gr.Markdown(
            f"# {TITLE} v{__version__}\n"
            f"{SUBTITLE}"
        )
        with gr.Row():
            with gr.Column(scale=1):
                audio_in = gr.Audio(label="Input (AI-generated audio)", type="filepath")
                strength = gr.Slider(0, 100, value=60, step=5,
                                     label="Processing strength")
                hf_start = gr.Slider(2000, 8000, value=4000, step=500,
                                     label="Artifact band start (Hz)")
                comb_freq = gr.Number(value=75.0, precision=1,
                                      label="Codec frame rate (Hz) - 75 = EnCodec, 50 = many SoundStream")
                use_comb = gr.Checkbox(value=True, label="Comb-ripple flattener (frame-rate AM + harmonics)")
                use_unfreeze = gr.Checkbox(value=True, label="Frozen-noise unfreezer + dither")
                use_echo_guard = gr.Checkbox(value=True, label="Pre-echo guard (ghost echo before hits)")
                use_transient = gr.Checkbox(value=True, label="Transient restoration")
                use_demi = gr.Checkbox(value=True, label="De-metal: adaptive spectral gate (music-following noise)")
                use_bandlimit = gr.Checkbox(value=True, label="Adaptive air-band roll-off")
                gr.Markdown(
                    "**AI neural stage** (Demucs separation + per-stem "
                    "cleanup - best quality, heavy: first run downloads "
                    "the model, several minutes on CPU per track)\n\n"
                    + _neural_device_line()
                )
                neural_on = gr.Checkbox(value=False, label="Enable AI neural stage")
                model_name = gr.Dropdown(
                    choices=["htdemucs", "htdemucs_ft"],
                    value="htdemucs",
                    label="Model - htdemucs = faster, htdemucs_ft = best quality",
                )
                residual_pct = gr.Slider(0, 100, value=30, step=5,
                                         label="Demucs residual retention (%) - "
                                               "keeps room/pads, tames metallic HF")
                btn_analyze = gr.Button("Analyze artifacts", variant="secondary")
                gr.Markdown("*Analyze is optional and purely informational - "
                            "processing performs its own internal analysis.*")
                btn_process = gr.Button("Process / Remove artifacts", variant="primary")
                btn_cancel = gr.Button("Cancel processing", variant="stop",
                                       interactive=False)
            with gr.Column(scale=2):
                analysis_plot = gr.Plot(label="Analysis")
                analysis_report = gr.Textbox(label="Artifact report", lines=5)
                audio_out = gr.Audio(label="Processed output", type="filepath")
                compare_plot = gr.Plot(label="Before / after")
                process_report = gr.Textbox(label="Processing report", lines=6)
                history_box = gr.Textbox(label="Run history (newest first - "
                                               "player resets to 0:00 per run)",
                                         lines=6, interactive=False)

        btn_analyze.click(run_analysis, inputs=[audio_in, hf_start],
                          outputs=[analysis_plot, analysis_report, comb_freq])
        btn_process.click(run_processing,
                          inputs=[audio_in, strength, hf_start, comb_freq,
                                  neural_on, model_name, residual_pct,
                                  use_comb, use_unfreeze, use_transient,
                                  use_bandlimit, use_echo_guard, use_demi],
                          outputs=[audio_out, compare_plot, process_report,
                                   history_box, btn_process, btn_analyze,
                                   btn_cancel])
        btn_cancel.click(cancel_run, outputs=[process_report])
        gr.Markdown(
            f"<div style=\"margin-top: 0px; padding-top: 6px; "
            f"border-top: 1px solid var(--border-color-primary);\">"
            f"v{__version__} · by <b>{AUTHOR}</b> · "
            f"<a href=\"{GITHUB_URL}\">GitHub</a> · "
            f"<a href=\"{DONATE_URL}\">☕ Support</a></div>"
        )
    return demo


def launch():
    build().launch(inbrowser=True)


if __name__ == "__main__":
    launch()
