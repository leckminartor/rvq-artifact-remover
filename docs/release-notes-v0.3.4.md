Bugfix release - the processed-audio player reliably resets to 0:00 after each
run, even when the previous result was played.

## Fixed

- Gradio keeps the same `<audio>` element and its `currentTime` when only the
  file value changes, so clearing the value did not reset playback. Each run
  now gives the Audio component a fresh `key` (`audio-out-1`, `audio-out-2`,
  ...), forcing the browser to remount it as a brand-new element that always
  starts at 0:00 and never caches the previous position.

## Verification

App UI builds cleanly; all 6 tests pass.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
