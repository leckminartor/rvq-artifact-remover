Bugfix release - the app starts cleanly again after a version conflict.

## Fixed

- The app crashed at startup with `Too much data for declared Content-Length`
  whenever the browser requested Brotli compression. Gradio's
  `BrotliMiddleware` is incompatible with the installed starlette and sends
  more bytes than the declared Content-Length. The middleware is now swapped
  for a pass-through at import time in `rvq_remover/app.py`, so responses are
  served uncompressed (fine for a local app). Verified with
  `Accept-Encoding: gzip, deflate, br` -> HTTP 200.

## Verification

App UI builds and serves cleanly (HTTP 200, including Brotli-negotiated
requests); all 6 tests pass.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
