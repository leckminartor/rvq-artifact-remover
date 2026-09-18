Bugfix release - the processed-audio player now reliably jumps back to 0:00
after each run.

## Fixed

- The output player is explicitly cleared with `gr.update(value=None)` when
  a processing run starts (a plain `None` yielded to the Audio component is
  treated by Gradio as "no change", so the old result kept playing). The
  finished run then loads a fresh, uniquely named output file that starts
  from the beginning.

## Verification

App UI builds cleanly; all 6 tests pass.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
