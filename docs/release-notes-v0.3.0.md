De-hall / de-metal release - targets the remaining "AI hall" character
(the bright/tinny/metallic background that betrays AI-generated music).

## Added

- **De-metal adaptive spectral gate** - codec noise that follows the music
  is not static and slipped past the frozen-bin unfreezer; it is heard as
  a metallic sheen or a thin artificial hall. A per-bin noise floor is
  estimated with rolling minimum statistics; Wiener-style over-subtraction
  with temporally smoothed gains attenuates the sheen. Sustained tones are
  protected by the phase-lag test, treated bins are re-naturalized with
  TPDF dither at independent phase.
- **Pre-echo guard** - RVQ codecs smear sharp hits into the preceding
  quiet frames (reverse-reverb ghost). Those frames are attenuated on the
  HF band while the hit frame itself stays untouched.
- **Comb harmonics** - the comb-ripple flattener now also notches the
  2x/3x harmonics of the codec frame rate.
- **Demucs residual cancellation** - the mix-minus-stems residual (hall /
  artifact share) is HF-tamed and partially retained instead of discarded,
  so room and pad content survive. New "Demucs residual retention" control
  in the app (default 30 %) and `--residual-keep` in the CLI.

## Changed

- Frozen-noise energy (HF) after the DSP stages drops to 0.144 on the
  synthetic benchmark (was 0.378); with the neural stage it drops to
  0.003 (was 0.319). Comb depth end-to-end: 0.512 -> 0.139.

## New controls

- App checkboxes: "Pre-echo guard (ghost echo before hits)",
  "De-metal: adaptive spectral gate (music-following noise)".
- App slider: "Demucs residual retention (%)".
- CLI flags: `--no-echo-guard`, `--no-demi`, `--residual-keep`.

## Verification

All 5 tests pass (`pytest tests/ -v`).

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
