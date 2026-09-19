Bugfix release - processing works again after the player-reset script.

## Fixed

- Clicking *Process* crashed with `None` slider values
  (`TypeError: '<' not supported between instances of 'NoneType' and 'int'`).
  The v0.3.6 browser reset script returned `undefined`, and Gradio feeds the
  JS return value back as the event inputs, nulling every slider. The script
  now returns the incoming `data` unchanged while still pausing and resetting
  all `<audio>`/`<video>` elements to 0:00 (including elements inside shadow
  DOM).

## Verification

App UI builds and serves cleanly; all 6 tests pass.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
