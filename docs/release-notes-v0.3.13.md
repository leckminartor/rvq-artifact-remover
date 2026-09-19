Bugfix release - the output player reliably resets to 0:00 on every run.

## Fixed

- The key remount alone did not force a playback reset in Gradio 6.27 (the
  element's `currentTime` survived), and a `js=` handler on the processing
  click corrupted the slider inputs. A dedicated **js-only event** (no
  backend fn, no inputs - a pure browser script that Gradio runs entirely in
  the frontend) now pauses every audio/video element and sets
  `currentTime = 0` when *Process* is clicked, before the normal processing
  event fires.

## Verification

App UI builds and serves cleanly; all 6 tests pass.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
