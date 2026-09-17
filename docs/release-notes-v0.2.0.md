Performance release - the processing pipeline is now several times faster.

## Changed

Measured on a 2-minute stereo track (RTX 3060), the full DSP + AI neural
stage dropped from ~4 minutes to **~36 seconds**:

- Envelope extraction for the comb stage, analysis and frame-rate detection
  now uses a decimated rectify + low-pass envelope instead of a full-rate
  Hilbert transform (~10x faster per band, same detection quality).
- Transient restoration now uses spectral-flux transient detection instead of
  the much more expensive HPSS decomposition.
- The AI neural stage processes the four stems in parallel and no longer
  recomputes full analysis metrics per stem.
- Stereo channels are processed in parallel.
- Demucs runs in FP16 on CUDA GPUs, with automatic fallback to FP32.

## Added

- Live stage progress in the app ("DSP - channel 1/2: comb stage",
  "AI - Cleaning stem: drums...") instead of a static status line.
- Cancel now also interrupts the DSP stages, not only the neural stage.

## Verification

All tests pass; artifact metrics are unchanged in direction and strength
(synthetic benchmark end-to-end: comb depth -69%, frozen-noise energy -51%).

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
