Bugfix release - *Process* works again after removing the broken `js=` handler.

## Fixed

- Clicking *Process* no longer fails with `None` slider values
  (`TypeError: '<' not supported between instances of 'NoneType' and 'int'`).
  Root cause: Gradio's `js=` handler must return the full list of inputs;
  the browser script returned a wrong value, which nulled every slider. The
  `js=` handler is removed entirely. The output player reset to 0:00 is
  handled server-side via the per-run `key` remount (introduced in v0.3.5),
  which is deterministic and does not touch event inputs.

## Verification

App UI builds and serves cleanly; all 6 tests pass.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
