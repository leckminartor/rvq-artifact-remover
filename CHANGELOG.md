# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
