Bugfix release - the processed-audio player reliably jumps back to 0:00 after
every run, even when the previous result had been played.

## Fixed

- The player reset did not survive Gradio's yield coalescing: clearing the Audio
  component from inside the long-running generator was merged with the final
  file yield, so the `src` swap kept the old `currentTime`. The clear is now a
  dedicated `clear_output()` event chained with `.then()` before processing,
  so the player always transitions *empty -> new file* and starts at 0:00.

## Verification

App UI builds cleanly; all 6 tests pass.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
