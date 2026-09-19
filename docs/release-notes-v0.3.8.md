Bugfix release - processing works again after a gradio regression.

## Fixed

- After upgrading to the very new gradio 6.28.0, the *Process* run crashed in
  the preprocessing step: sliders were passed as `None` instead of their
  numeric value (`TypeError: '<' not supported between instances of
  'NoneType' and 'int'`). The project venv is pinned back to the proven
  gradio 6.27.0 and the `[app]` extra is capped (`gradio>=4.0,<6.28.0`) so a
  future `pip install` cannot reintroduce the regression. The BrotliMiddleware
  bypass from v0.3.7 stays in place.

## Verification

App UI builds and serves cleanly (HTTP 200, including Brotli-negotiated
requests); all 6 tests pass.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
