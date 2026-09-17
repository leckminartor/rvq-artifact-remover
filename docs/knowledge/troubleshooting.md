# Troubleshooting – bekannte Bugs, Fixes und Heuristiken

Volltextsuche: `rg -i "begriff" docs/knowledge/troubleshooting.md`

## Behobene Bugs (Chronologie)

### Broadcast-Shape-Fehler "(2,10583040) (2,10583041)"
- **Symptom:** `operands could not be broadcast together with shapes
  (2,10583040) (2,10583041) (2,10583040)`
- **Ursache:** Längen-Mismatch nach Resample/Kadenzierung (Off-by-one zwischen
  Kanälen/Resampling-Stufen).
- **Fix:** konsequentes `_match_length()` auf Original-Länge in neural.py;
  istft immer mit `length=len(x)` aufrufen. Regel: Nach JEDER Resample-/STFT-
  Runde Längen hart angleichen.

### pip tomllib lehnt UTF-8-BOM ab
- **Symptom:** `pip install -e .` schlägt fehl ("tomllib rejects BOM").
- **Ursache:** UTF-8-BOM am Dateianfang (Windows-Editor).
- **Fix:** BOM aus pyproject.toml, CITATION.cff, README.md, __init__.py strippen
  (Commit `50f9d34`). Heuristik: Neue Windows-Dateien ohne BOM speichern;
  bei TOML-Parse-Fehlern zuerst BOM prüfen (`Format-Hex`-Byte 0xEF 0xBB 0xBF).

### Dopplung "by Klaus Perner (DJ LECK)" + Leerraum überm Footer
- **Fix:** Autor nur im Footer; Markdown-Horizontalrule durch CSS-Border ersetzt
  (margin-top 0, padding-top 6px). Commits `6863197`, `2002488`.

### Version wurde bei Release nicht angehoben
- **Lektion:** Release-Checkliste: pyproject.toml + __init__.py + CITATION.cff
  gemeinsam bumpen, dann committen/taggen/pushen (siehe decisions.md).

### scipy: `gaussian_filter1d` akzeptiert keine Sigma-Tupel
- **Symptom:** `TypeError: float() argument must be a string or a real number,
  not 'tuple'` in demi_gate.
- **Fix:** Für 2D-Glättung `ndimage.gaussian_filter(...)` (nimmt Tuple) statt
  `gaussian_filter1d` (nur Skalar) verwenden.

### Post-Echo-Dämpfung beschädigte Drum-Tails
- **Symptom:** Test "transient frame was damaged" – dämpft man Frames NACH dem
  Hit, sterben Cymbal-Tails.
- **Fix:** echo_guard ist Pre-only; Post-Anteil bewusst weggelassen (übernimmt
  nichts – transient_boost ist schon aggressiv genug). Lektion: Ghost-Echo
  problematisch = vor dem Hit, nicht danach.

## Heuristiken / Fallstricke

- **PowerShell 5.1:** kein `&&` (nutze `;` bzw. `if ($?)`); kein `head`/`tail`/
  `ls -la` → `Get-Content -TotalCount`, `Select-Object -First/-Last`,
  `Get-ChildItem`. Pipes von nativen Tools erzeugen gern NativeCommandError
  im stderr – Ausgabe ggf. filtern statt 2>&1-Blindflug.
- **Python-Ausgabe unter Windows (cp1252):** Unicode-Zeichen (☕, Umlaute) im
  stdout crashen → `python -X utf8` oder Dateien explizit utf-8 schreiben.
- **Session-JSON:** 12 MB, nicht komplett laden; gezielt parsen (utf-8-sig!).
- **ThreadPoolExecutor + status_cb:** Status-Callback kann interleaved kommen;
  in der App puffert ein holder-dict den letzten Status (thread-safe genug).
- **Tests mit CUDA:** htdemucs-Test braucht torch+demucs; sonst importorskip.
  ComplexHalf-Warnung von torch ist harmlos.
- **Kontextfenster-Überläufe:** Lieber AGENTS.md + docs/knowledge/ pflegen als
  den Verlauf halten. Cloudflare-"Provider returned error" = Provider-Überlast/
  Kontext zu groß → Session neu starten, aus AGENTS.md wieder einsteigen.

## Diagnose-Reihenfolge bei App-Fehlern

1. Fehlermeldung ist `Error: <exc>` im Process-Report → erst `pytest tests/ -v`.
2. DSP-only testen (`--neural` weglassen) → liegt's an engine oder neural?
3. Bei Shape-Fehlern: Längen-Kette prüfen (load → resample → stems → match_length).
4. Bei CUDA-Problemen: FP32-Fallback greift automatisch; Device-Zeile in der App prüfen.
