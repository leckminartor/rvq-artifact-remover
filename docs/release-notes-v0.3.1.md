UX release - easier A/B testing of different processing modes.

## Added

- **Mode-tagged output files** - every run is written as
  `<name>_<stages>_derq.wav` with a suffix encoding the active
  pipeline (`c` comb, `u` unfreeze, `e` echo guard, `t` transient,
  `d` de-metal, `b` bandlimit, `-ai`/`-ai-ft` neural stage), e.g.
  `song_cuetdb-ai_derq.wav`. Every run produces a unique, self-
  describing file - ideal for loading the same track with several
  different settings and comparing the results.
- **Run history panel** in the app (newest first, last 12 runs):
  timestamp, output file, strength, model and residual retention.
- **Player reset to 0:00** - the output player is cleared at run
  start and each finished run loads a fresh, unique file, so the
  player always starts from the beginning.

## Verification

All tests pass; the app UI builds cleanly.

**Full changelog:** [CHANGELOG.md](https://github.com/leckminartor/rvq-artifact-remover/blob/main/CHANGELOG.md)
