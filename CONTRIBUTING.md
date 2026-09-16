# Contributing

Thanks for your interest in improving the RVQ Artifact Remover!

## Development setup

```bash
git clone https://github.com/leckminartor/rvq-artifact-remover.git
cd rvq-artifact-remover
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -e ".[app,dev]"
```

For the AI neural stage additionally:

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128   # NVIDIA GPU
# pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu   # CPU only
pip install demucs
```

## Running the tests

```bash
pytest tests/ -v
```

`test_neural.py` is skipped automatically when torch/demucs are not installed.
Do not commit any audio files.

## Guidelines

- Keep the DSP engine (`rvq_remover/engine.py`) free of heavy third-party
  dependencies beyond numpy/scipy/librosa so the base install stays light.
- Every processing stage must be signal-adaptive (detect before you modify)
  and must preserve length, loudness balance and peak safety.
- Verify changes against the synthetic damage model in
  `tests/test_synthetic.py` - metrics must improve, not just "sound different".
- Update `CHANGELOG.md` for any user-visible change.

## Reporting issues

Include: input format (sample rate, codec/model that produced it), the
artifact report from the analysis view, and console output. Audio files are
rarely necessary - metric numbers usually suffice.
