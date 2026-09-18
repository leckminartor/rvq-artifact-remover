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

### CI-Mails: Fehlschlag-Mail kann veraltet sein
- **Fall (17.09.):** "CI: All jobs have failed"-Mail für alle 3 Python-Versionen,
  failed in 6–10 s – war der v0.1.2-Push (Run 35206160908, BOM-Bug), **bereits
  2 Minuten später durch Commit `50f9d34` behoben**. Der User bekam die Mail
  trotzdem noch zugestellt.
- **Vorgehen bei CI-Mails:** Erst `gh run list --limit 20` prüfen (ist der Run
  überhaupt der aktuellste?) → `gh run view <id> --log-failed` für Ursache.
  Fehlschlag < 15 s = Setup/Install-Problem (pip/checkout), NICHT Tests.
- **Guard:** `tests/test_repo_hygiene.py` prüft jetzt auf UTF-8-BOM in
  pyproject/CITATION/README/__init__ – kann CI nicht mehr schleichend brechen.

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

### Gradio-Audio-Player-Reset (v0.3.2 / v0.3.3)
- **Symptom:** Output-Player sprang nach einem weiteren Durchgang nicht auf 0:00,
  obwohl v0.3.1 `gr.update(value=None)` beim Laufstart setzte.
- **Ursache (v0.3.2):** `yield None` an `gr.Audio` gilt als "keine Änderung".
- **Ursache (v0.3.3, der eigentliche Kern):** Selbst `gr.update(value=None)`
  aus dem langlaufenden Generator wird von Gradio mit dem finalen Datei-Yield
  **koalesziert** – der Browser tauscht den `src` in-place und behält
  `currentTime`; die alte Position bleibt stehen.
- **Fix (v0.3.3):** Das Leeren als **eigenen Event-Schritt** vorschalten:
  `btn_process.click(clear_output, outputs=[audio_out]).then(run_processing, ...)`.
  So wechselt der Player garantiert *leer -> neue Datei* und startet bei 0:00.
- **Fix (v0.3.4, entscheidend):** Auch das war nicht genug – Gradio behält bei
  reinem `value`-Wechsel dasselbe `<audio>`-Element samt `currentTime`. Jeder
  Lauf vergibt jetzt einen frischen `key` (`gr.update(value=None, key=audio-out-N)`),
  wodurch der Browser das Widget neu remountet (neue Element-Identität) und bei
  0:00 startet. Faustregel: Bei persistierten Player-Zuständen → wechselnder
  `key` im `gr.update` erzwingt Remount.
