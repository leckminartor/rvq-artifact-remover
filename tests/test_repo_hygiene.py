"""Repo hygiene guards - catch packaging issues that broke CI before."""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_no_utf8_bom_in_packaging_files():
    # tomllib rejects a UTF-8 BOM; a BOM in pyproject.toml broke the CI
    # install step within seconds (GitHub run 35206160908, fixed in
    # commit 50f9d34). Guard against regressions.
    for name in ["pyproject.toml", "CITATION.cff", "README.md",
                 "rvq_remover/__init__.py"]:
        raw = (ROOT / name).read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{name} has a UTF-8 BOM"
