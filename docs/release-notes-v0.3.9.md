Bugfix release - the startup crash is fully resolved.

## Fixed

- The `Too much data for declared Content-Length` crash is gone. Root cause:
  some asset responses (e.g. the ~130 KB JS bundle) are sent with a
  `Content-Length` that is too small, which uvicorn/h11 rejects. The
  middleware injected in `rvq_remover/app.py` now strips the
  `Content-Length` header from all HTTP responses, so they use chunked
  transfer encoding instead. Verified: page (HTTP 200) and the largest JS
  asset (133 KB) load cleanly, even with `Accept-Encoding: br`.

## Verification

App UI builds and serves cleanly (page + JS assets, HTTP 200); all 6 tests
pass.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
