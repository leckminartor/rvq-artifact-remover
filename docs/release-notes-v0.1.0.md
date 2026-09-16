First public release of the RVQ Artifact Remover.

## Highlights

- **Offline DSP pipeline** for removing neural-codec (RVQ) quantization artifacts from AI-generated music:
  - Comb-ripple flattener - cancels codec frame-rate amplitude modulation (e.g. 75 Hz for EnCodec) on log-spaced HF sub-band envelopes
  - Frozen-noise unfreezer - detects temporally static quantization-noise bins (transient-trimmed robust std + phase-randomness tone protection) and re-naturalizes them with TPDF dither
  - Transient restoration - re-applies percussive gain lost to codec smearing
  - Adaptive air-band roll-off above the detected musical energy edge
- **Automatic codec frame-rate detection** (known-rate scan 10-125 Hz, prominence-ranked)
- **Optional AI neural stage** - Demucs (htdemucs / htdemucs_ft) source separation with per-stem targeted cleanup and artifact-aware recombination
- **Gradio desktop app** - analysis view with frozen-bin spectrogram overlay, before/after comparison, live progress, cancel support
- **CLI batch processor** (`rvq-remover`) and library API
- **GPU support** via CUDA torch wheels (auto-detected, verified on RTX 3060)

## Verification

Synthetic RVQ-damage benchmark: comb depth 0.610 -> 0.117 (DSP + AI stage), frozen-noise energy 0.704 -> 0.319. See `tests/test_synthetic.py`.

## Getting started

```
pip install -e ".[app,dev]"
rvq-remover-app
```

See the README for full installation (incl. GPU setup) and usage instructions.
