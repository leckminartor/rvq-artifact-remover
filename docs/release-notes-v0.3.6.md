Bugfix release - the processed-audio player reliably resets to 0:00 on every
new run, even after the previous result was played.

## Fixed

- Gradio preserves the `<audio>` element's `currentTime` across value/key
  changes, so server-side resets (value=None, remount keys) were not enough
  on their own. The *Process* button now runs a tiny browser script first that
  pauses every `<audio>` element and sets `currentTime = 0` before processing
  starts. Playback therefore always begins at 0:00.

## Verification

App UI builds cleanly; all 6 tests pass.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
