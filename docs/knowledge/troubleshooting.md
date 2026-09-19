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

### Eigenes `.venv` fehlt Neural-Deps → "No module named 'torch'" (18.09.)
- **Symptom:** Beim *Process*-Klick (KI-Stufe an) "Error: No module named 'torch'".
- **Ursache:** Das isolierte `.venv` (angelegt wegen gradio/starlette-Konflikt)
  wurde nur mit `pip install -e ".[app]"` befüllt – torch/demucs gehören zum
  `[neural]`-Extra und fehlten.
- **Fix:** In `.venv` nachinstallieren:
  `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128`
  + `pip install demucs`. Verifiziert: torch 2.11+cu128, CUDA auf RTX 3060 aktiv.
- **Lektion:** Nach Neuanlage des `.venv` IMMER `[neural]`-Deps prüfen
  (`python -c "import torch, demucs"`), sonst schlägt die KI-Stufe still fehl.

### Gradio-Audio-Player-Reset – finaler Yield muss `key` mitführen (v0.3.12)
- **Symptom:** Nach einem neuen Durchlauf stand der Output-Player weiterhin
  an der alten Position (z. B. 1:05) statt bei 0:00 – obwohl die App wieder
  läuft und der Process-Klick funktioniert.
- **Ursache:** Der finale Yield lieferte `out_path` als nackten String – ohne
  den frischen per-run `key`. Gradio behielt damit das alte `<audio>`-Element
  samt `currentTime`; der Key-Remount (v0.3.5) wurde durch den String-Yield
  wieder verworfen.
- **Fix (v0.3.12):** Finaler Yield liefert `gr.update(value=out_path, key=audio_key)`
  – die neue Datei lädt im frisch remounteten Element und startet bei 0:00.
- **Lektion:** Wenn man einen `key`-Remount verwendet, MÜSSEN ALLE
  nachfolgenden Yields dieses Elements denselben `key` mitschicken –
  ein nackter String (auch am Ende) hebt ihn auf.

### Gradio-Audio-Player-Reset – finaler Weg: js-only Event (v0.3.13)
- **Stand der Dinge:** key-Remount (v0.3.5/v0.3.12) allein erzwingt in Gradio
  6.27 KEINEN Playback-Reset (currentTime überlebt). `js=` am selben Event wie
  `fn` zerstört Inputs (v0.3.10/0.3.11). Der sichere Weg: ein **separates,
  js-only Event** ohne Backend-fn und ohne Inputs – Gradio führt es komplett
  im Browser aus, der Rückgabewert ist irrelevant:
  `btn_process.click(js="() => { ...a.pause(); a.currentTime = 0... }")` +
  normaler `btn_process.click(run_processing, ...)` für die Verarbeitung.
- **Lektion:** Browser-Seiteneffekte VOR einem Python-Event nie über `js=`
  am selben Event-Trigger (kollidiert mit Input-Vertrag) – sondern als
  eigenständiges js-only `.click()` registrieren.

### Gradio-`js=`-Handler zerstört Event-Inputs (v0.3.11)
- **Symptom:** *Process*-Klick meldet "Fehler", Traceback: `Expected a float,
  but the value passed was None` für Slider; `preprocess_data` →
  `slider.raise_if_out_of_bounds`.
- **Ursache:** Gradio's `js=`-Handler (Button) bekommt Inputs+Outputs als
  Argumente und MUSS die komplette Input-Liste zurückgeben. Ein falscher
  Rückgabewert (z. B. nur ein Wert / `undefined`) nullt alle Slider.
- **Fix (v0.3.11):** `js=`-Handler komplett ENTFERNT. Player-Reset auf 0:00
  läuft serverseitig über den per-run `key`-Remount (v0.3.5) – deterministisch,
  ohne Eingriffe in Event-Inputs.
- **Lektion:** Bei Gradio-BUTTON-Events mit Inputs: NICHT `js=` verwenden,
  wenn man nicht exakt die Input-Liste zurückspiegelt; serverseitige Lösung
  (key-Remount) ist robuster.

### gradio-Slider-Regression (6.28.0) – `None` statt Zahl (17.09.)
- **Symptom:** Beim *Process*-Klick crasht `preprocess_data` mit
  `TypeError: '<' not supported between instances of 'NoneType' and 'int'`
  ("Expected a float, but the value passed was None") – Slider liefern `None`.
- **Ursache:** gradio 6.28.0 (brandneu) übergibt Slider-Werte als `None`.
- **Fix:** gradio auf 6.27.0 gepinnt (`.venv`) + Obergrenze im `[app]`-Extra
  (`gradio>=4.0,<6.28.0`). Brotli-Patch (0.3.7) bleibt aktiv.
- **Lektion:** brandneue Gradio-Minor-Versionen bei solchen Apps nicht blind
  übernehmen; nach Upgrade IMMER den Slider-Preprocess-Pfad testen.

### gradio/starlette-Brotli-Konflikt beim App-Start (17.09.)
- **Symptom:** `RuntimeError: Response content longer than Content-Length`
  bzw. `h11 LocalProtocolError: Too much data for declared Content-Length` beim
  Laden der Seite (Traceback über `gradio/brotli_middleware.py` →
  `starlette/responses.py` → `uvicorn send`), noch bevor Verarbeitung läuft.
- **Ursache (korrigiert, v0.3.9):** NICHT Brotli allein – einige Asset-Responses
  (z. B. das ~130-KB-JS-Bundle) werden mit einem zu kleinen `Content-Length`
  gesendet; uvicorn/h11 lehnt das ab. Mein erster `GET /`-Test war fehl-positiv
  grün, weil nur die kleine HTML-Seite geladen wurde; der Browser lädt danach
  die großen JS-Bundles → Crash.
- **Fix (v0.3.9, endgültig):** Injizierte Middleware in `rvq_remover/app.py`
  entfernt den `Content-Length`-Header aus ALLEN HTTP-Antworten → uvicorn nutzt
  Chunked-Transfer-Encoding. Verifiziert: Seite + größtes JS-Asset (133 KB) mit
  `Accept-Encoding: br` → HTTP 200.
- **Lektion:** Lokale Gradio-Apps IMMER auch mit Asset-Requests testen (JS/CSS
  aus der HTML parsen und einzeln laden) + `Accept-Encoding: br` – nur `GET /`
  reicht nicht.

### Gradio-`js=`-Rückgabewert killt Slider-Inputs (v0.3.10)
- **Symptom:** Beim *Process*-Klick: `Expected a float, but the value passed was
  None` für Slider (nachdem der Content-Length-Start-Fix griff). Traceback über
  `preprocess_data` → `slider.raise_if_out_of_bounds`.
- **Ursache:** Das eigene `js=`-Skript (Player-Reset, v0.3.6) gab `undefined`
  zurück. Gradio interpretiert den JS-Rückgabewert als neue Event-Inputs →
  ALLE Slider/Componenten wurden `None`.
- **Fix (v0.3.10):** JS gibt `data` (die eingehenden Inputs) unverändert
  zurück: `(data) => { ...reset audio...; return data; }`.
- **Lektion:** Ein `js=`-Handler muss IMMER `data` zurückgeben, sonst werden
  Inputs zerstört. Kein `() => {}` / kein `undefined`-Return bei Events mit
  Inputs.

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
- **Fix (v0.3.5, tatsächlich wirksam):** Der v0.3.4-Key wurde durch die
  Zwischen-Yields von `run_processing` zunichte gemacht (dort stand
  `gr.update(value=None)` OHNE Key → frischer Key verworfen, altes Element samt
  `currentTime` blieb). Jetzt verwaltet `run_processing` den Key selbst und
  liefert ihn in JEDEM Audio-Yield: Start = leerer Remount mit Key, Ende =
  neue Datei im selben frisch remounteten Element → immer 0:00. Lektion: Ein
  frischer `key` nützt nur, wenn er in ALLEN nachfolgenden Yields des
  Elements beibehalten wird.
- **Fix (v0.3.6, final zuverlässig):** Gradio hält die `currentTime` des
  `<audio>`-Elements selbst über `value`-/`key`-Wechsel hinweg hart fest –
  serverseitige Resets reichen nicht. Der zuverlässige Weg ist ein
  **Browser-JS-Reset über den `js=`-Parameter des Click-Events**:
  `document.querySelectorAll('audio').forEach(a => { a.pause(); a.currentTime = 0; })`
  – läuft beim Klick VOR der Verarbeitung. Faustregel: Bei Gradio-Audio-
  Positionen ist serverseitig nichts garantiert → JS auf dem Click-Event nutzen.
- **Fix (v0.3.6, final zuverlässig):** Selbst konsistente `key`s remounten die
  Wiedergabeposition nicht garantiert – Gradio hält `currentTime` hart. Der
  zuverlässige Weg ist ein **Browser-JS-Reset über den `js=`-Parameter von
  `btn_process.click`**: `document.querySelectorAll('audio').forEach(a => { a.pause();
  a.currentTime = 0; })` läuft beim Klick VOR der Verarbeitung. Lektion: Bei
  Gradio-Audio-Positionen ist serverseitig nichts garantiert → JS auf dem
  Click-Event nutzen.
