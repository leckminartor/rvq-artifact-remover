Bugfix release - the output player reliably starts at 0:00 after each run.

## Fixed

- The final yield in `run_processing` returned the output file path as a
  plain string, which dropped the fresh per-run `key` and kept the old
  element's playback position. It now returns
  `gr.update(value=out_path, key=audio_key)`, so the new file loads in the
  freshly remounted element and always starts at 0:00.

## Verification

App UI builds and serves cleanly; all 6 tests pass.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
