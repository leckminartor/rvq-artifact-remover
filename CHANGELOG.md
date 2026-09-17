# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-09-17

### Added

- De-hall / de-metal package targeting the remaining "AI hall" character
  (bright/tinny/metallic background that betrays AI-generated music):
  - De-metal adaptive spectral gate: per-bin noise floor from rolling
    minimum statistics, Wiener-style over-subtraction with temporally
    smoothed gains removes the music-following metallic sheen that the
    static-bin unfreezer missed. Sustained tones are protected by the
    phase-lag test; treated bins are re-naturalized with TPDF dither.
  - Pre-echo guard: attenuates codec window-leakage ghost echo in quiet
    frames before sharp transients (hit frames untouched).
  - Comb-ripple flattener now also notches the 2x/3x harmonics of the
    codec frame rate.
  - Demucs residual cancellation: the mix-minus-stems residual (hall /
    artifact share) is HF-tamed and partially retained (default 30 %)
    instead of discarded, so room and pad content survive. New
    "Demucs residual retention" control in the app; `--residual-keep`
    in the CLI.

### Changed

- Synthetic benchmark improvement: frozen-noise energy (HF) now drops to
  0.144 after DSP stages (was 0.378) and to 0.003 with the neural stage
  (was 0.319). Comb depth end-to-end 0.512 -> 0.139.

### Added (controls)

- App/CLI toggles: "Pre-echo guard", "De-metal adaptive gate";
  CLI flags `--no-echo-guard`, `--no-demi`, `--residual-keep`.

## [0.2.0] - 2026-09-17

### Changed

- Major performance optimisation - measured on a 2-minute stereo track
  (RTX 3060): full DSP + AI neural stage now takes ~36 s instead of ~4 min.
  - Envelope extraction for the comb stage, analysis and frame-rate
    detection now uses a decimated rectify + low-pass envelope instead of a
    full-rate Hilbert transform (~10x faster per band, same detection
    quality).
  - Transient restoration now uses spectral-flux transient detection
    instead of the much more expensive HPSS decomposition.
  - The AI neural stage processes the four stems in parallel and no longer
    recomputes full analysis metrics per stem.
  - Stereo channels are processed in parallel.
  - Demucs runs in FP16 on CUDA GPUs, with automatic fallback to FP32.

### Added

- Live stage progress in the app ("DSP - channel 1/2: comb stage",
  "AI - Cleaning stem: drums...") instead of a static status line.
- Cancel now also interrupts the DSP stages, not only the neural stage.

### Removed

- Dead code in the frame-rate detector.

## [0.1.2] - 2026-09-17

### Fixed

- Removed the oversized blank space above the app footer credit line
  (markdown rule replaced with a tight CSS border).

## [0.1.1] - 2026-09-17

### Added

- App header/footer now show the version and author credit
  ("by Klaus Perner (DJ LECK)") plus GitHub and donation links.
- App shows the detected neural-stage device ("CUDA - RTX 3060" / "CPU")
  before processing.
- "Analyze artifacts" now automatically applies the strongest detected
  codec frame rate to the "Codec frame rate" setting (only when a clear
  comb line is present; otherwise the user setting is preserved).

### Fixed

- Duplicate author line removed from the app header.

## [0.1.0] - 2026-09-16

### Added

- Offline DSP pipeline for removing neural-codec (RVQ) quantization artifacts:
  - Comb-ripple flattener: cancels codec frame-rate amplitude modulation
    (e.g. 75 Hz for EnCodec) on log-spaced HF sub-band Hilbert envelopes.
  - Frozen-noise unfreezer: detects temporally static quantization-noise bins
    (transient-trimmed robust std + phase-randomness test that protects
    sustained tones) and re-naturalizes them with TPDF dither.
  - Transient restoration: re-applies percussive gain lost to codec smearing.
  - Adaptive air-band roll-off above the detected musical energy edge.
- Automatic codec frame-rate detection (10-125 Hz scan, top-3 candidates
  reported in the UI analysis).
- Optional AI neural stage: Demucs (htdemucs / htdemucs_ft) source separation
  with per-stem targeted cleanup and artifact-aware recombination.
- Gradio desktop app: analysis view with frozen-bin spectrogram overlay,
  before/after comparison, live progress, cancel support, error reporting.
- CLI batch processor (`rvq-remover`) with pipeline toggles.
- Synthetic RVQ-damage verification suite (`tests/`).
- GPU support via CUDA torch wheels (auto-detected, verified on RTX 3060).
