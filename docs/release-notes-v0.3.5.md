Bugfix release - the processed-audio player reliably resets to 0:00 after each
run.

## Fixed

- The v0.3.4 per-run `key` was being neutralized: `run_processing` kept
  yielding plain `gr.update(value=None)` between progress updates, which
  dropped the fresh key and preserved the old `<audio>` element's
  `currentTime`. Now `run_processing` manages the per-run key itself and
  applies it to every audio yield - an empty remount at run start and the
  fresh file load in that same remounted element at the end. Playback always
  starts at 0:00, even after the previous result was played.

## Verification

App UI builds cleanly; all 6 tests pass.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
