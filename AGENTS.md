# Projekt-Kontext (Memory) – RVQ Artifact Remover

> Diese Datei dient als langlebiger Speicher für AI-Sessions.
> Bei vollen Kontextfenstern: Diese Datei lesen, dann weiterarbeiten.
> **Wissensdatenbank mit Details (FAQ, Entscheidungen, Bugs, Chat-Rohverlauf):**
> `docs/knowledge/` – Volltextsuche mit `rg -i "begriff" docs/knowledge/` oder
> `Select-String -Path docs\knowledge\*.md -Pattern "begriff"`. Bei Detailfragen
> zuerst dort nachschlagen, bevor die 12-MB-Session-JSON geparst wird.

## Projekt
- **Name:** RVQ Artifact Remover v0.3.0
- **Repo:** https://github.com/leckminartor/rvq-artifact-remover (remote `origin`, Branch `main`)
- **Lokaler Pfad:** `C:\Users\klaus\Documents\Default Project\rvq_cleaner`
- **Autor:** Klaus Perner (DJ LECK), PayPal: https://paypal.me/klausminator
- **Lizenz:** MIT
- **Ziel:** Offline-Entfernung von neuralen Codec (RVQ) Quantisierungsartefakten
  (EnCodec/SoundStream/DAC/X-Codec) aus KI-Musik (Suno, Udio, MusicGen, YuE …):
  Kammfilter-Buzz (codec frame-rate AM), "eingefrorene" metallische Rauschbins,
  Pre-Echo-Ghosts, musikfolgendes metallisches Rauschen (KI-Hall),
  verschmierte Transienten, künstliches Air-Band.

## Architektur (Python 3.10+, Windows-Entwicklungsumgebung)
- `rvq_remover/engine.py` – DSP-Kern (Pipeline in dieser Reihenfolge):
  1. `comb_notch()`: notcht Frame-Rate-AM **inkl. 2x/3x-Harmonischen** (seit v0.3.0,
     per-harmonische Tiefe k/h, Glättung oberhalb 3x-Rate).
  2. `unfreeze_frozen()`: statische Bins (robust std < 4.5 dB UND tone-likeness < 0.5)
     → Dämpfung + TPDF-Dither (SEED=20260916).
  3. `echo_guard()`: Pre-Echo-Guard (seit v0.3.0) – dämpft Quiet-Frames vor
     Flux-Peaks (HF-Band, 5 Frames, cap 0.6, Hit-Frame unangetastet).
  4. `transient_boost()`: Spectral-Flux-Transienten-Boost.
  5. `demi_gate()`: De-Metal-Adaptive-Gate (seit v0.3.0) – Minimum-Statistics-
     Noise-Floor (Power-Domain, 0.6-s-Fenster, bias 2.0) + Wiener-Over-Subtraction
     (k=0.9*strength), Gains geglättet (gaussian 1.5/4), Ton-Schutz via
     `_tone_likeness` >= 0.5, TPDF-Dither-Re-Injektion (0.35*mag*m).
  6. `bandlimit()`: Shelf ab Energiekante, max 6 dB.
  - `detect_comb_freq()`: bekannte Codec-Frameraten (12.5–125 Hz), Prominenz-Ranking.
  - `_band_env()`: Rectify+Lowpass+Decim (ENV_DECIM=8, cutoff 240 Hz).
  - `process()`: RMS-Ausgleich (clip 0.5–2.0), Peak 0.999, ThreadPoolExecutor
    pro Kanal, `cancel_check`/`status_cb`; Params: use_comb/unfreeze/transient/
    bandlimit/**echo_guard/demi**.
- `rvq_remover/neural.py` – Optionale KI-Stufe:
  - Demucs htdemucs/htdemucs_ft, FP16-CUDA (Fallback FP32), 4 Stems parallel
    (`STEM_CFG`: bass ohne Comb, drums mehr Transienten).
  - **Residual-Cancellation (seit v0.3.0)**: `residual = mix − Σ(stems)` wird
    per `_tame_residual()` (bandlimit ab hf_start*1.8) gezähmt und anteilig
    zurückgemischt (`keep = residual_keep * (1 − 0.5*strength)`, default 0.3).
    App-Slider "Demucs residual retention (%)", CLI `--residual-keep`.
- `rvq_remover/app.py` – Gradio-App: Analyse mit Frozen-Overlay, A/B, Auto-
  Frame-Rate, Live-Fortschritt, Cancel; neue Checkboxes (Pre-echo guard,
  De-metal gate) + Residual-Slider.
- `rvq_remover/cli.py` – Flags: --no-comb --no-unfreeze --no-transient
  --no-bandlimit --no-echo-guard --no-demi --residual-keep --neural --model.
- `tests/test_synthetic.py`: 4 Tests (Pipeline, Frame-Rate-Detection,
  demi_gate attenuiert Rauschen/schützt Ton, echo_guard trimmt Leakage/
  schont Hit). `tests/test_neural.py`: End-to-End (auto-skip ohne torch).
- `.github/workflows/ci.yml` – CI; `pyproject.toml` v0.3.0.

## Versionshistorie (Tags: v0.1.0 … v0.3.0 – released & gepusht)
- v0.1.0 (16.09.): initiale DSP-Pipeline + Gradio-App + CLI + Tests.
- v0.1.1: Auto-Frame-Rate nach Analyse, Versions-/Autor-Footer, Device-Status.
- v0.1.2: Footer-Abstands-Fix; BOM-Strip-Fix (pip tomllib).
- v0.2.0 (17.09., `7a850c4`): 5-7x schneller: decimierte Envelopes, Spectral-
  Flux-Transienten, parallel Stems/Kanäle, FP16-CUDA, Live-Fortschritt, Cancel.
- v0.3.0 (17.09.): **De-Hall/De-Metal-Paket** – demi_gate (Minimum-Statistics-
  Wiener-Gate gegen musikfolgendes Metallisch-Rauschen), echo_guard (Pre-Echo),
  Comb-Harmonischen (2x/3x), Demucs-Residual-Cancellation (residual_keep).
  Benchmark: Comb 0.512→0.222 (DSP) →0.139 (KI); Frozen 0.704→0.144→**0.003**.

## Aktueller Status
- **Stand: 18.09. – Session-Abschluss. Alle Arbeit ist committed/gepusht; der
  Repo-Stand auf GitHub (main) ist die Wahrheit. Voriges LLM wechselt wegen
  leeren OpenRouter-Guthabens – neue Session: AGENTS.md lesen (wird meist
  automatisch injiziert, sonst vom User auffordern lassen) + bei Detailfragen
  docs/knowledge/ durchsuchen; Session-JSON nur gezielt parsen.**

### Versions-/Release-Stand
- **v0.3.1 (latest, 18.09):** Modus-Kürzel im Output-Dateinamen
  (`<name>_<stages>_derq.wav`; c/u/e/t/d/b + -ai/-ai-ft), Run-Historie-Panel
  (12 Einträge, newest first), Player-Reset auf 0:00 pro Lauf.
  Release: https://github.com/leckminartor/rvq-artifact-remover/releases/tag/v0.3.1
- **v0.3.0 (17.09):** De-Hall/De-Metal-Paket – demi_gate, echo_guard,
  Comb-Harmonischen (2x/3x), Demucs-Residual-Cancellation (residual_keep,
  App-Slider). Release v0.3.0 veröffentlicht.
- Tags: v0.1.0, v0.1.1, v0.1.2, v0.2.0, v0.3.0, v0.3.1 – alle released & gepusht.
- **CI:** grün (6 Tests, inkl. neuem Guard `tests/test_repo_hygiene.py` gegen
  UTF-8-BOM). Veraltete CI-Fail-Mail vom 17.09 (v0.1.2-Push) war schon durch
  Commit `50f9d34` behoben – nichts zu tun.

### Am 17./18.09. dazugekommen (Übersicht)
1. Wissensdatenbank `docs/knowledge/` (faq.md, decisions.md, troubleshooting.md,
   session-user-log.md auto-generiert via `scripts/export_user_log.py`).
2. Offene Nutzerfrage "KI-Hall/Echo reduzieren" → in v0.3.0 umgesetzt;
   Strength-Wirkung auf alle Stufen dokumentiert (faq.md).
3. A/B-Test-Workflow im App-Chat erklärt: Gleicher Input bleibt geladen, jeder
   Lauf startet vom Original (kein Chaining), Output-Player pro Lauf neu.

### Offene Themen / Roadmap (unverändert)
1. WPE-Dereverberation als eigene Stufe (echter generativer Hall).
2. Generative Band-Extension (z. B. AudioSR) fürs Air-Band.
3. Real-time-Modus der DSP-Stufen.
4. Per-Stem-Strength-Presets in der UI.
5. Weitere Metriken (Stereo-Image-Stagnation, Modulationsrauschen).
6. Ungetrackt & NICHT committen: `ai-music-rvq-artifact-removal-app.json` (12 MB
   Session-Archiv), `output/`-Audio.

## Offene Themen / Roadmap (aus README)
1. Real-time-Modus für DSP-Stufen.
2. Per-Stem-Strength-Presets in der UI.
3. Weitere Metriken (Stereo-Image-Stagnation, Modulationsrauschen).
4. Optionales Band-Extension-Modell (z. B. AudioSR) für HF-Wiederherstellung.
5. Optional: Dereverberation (WPE) als eigene Stufe gegen echten generativen Hall.

## Nutzer-Verlauf (extrahiert aus ai-music-rvq-artifact-removal-app.json)
Wichtige Anforderungen/Entscheidungen des Users (chronologisch):
1. Ziel: professionelle App zum Entfernen von RVQ-Artefakten; Ergebnis soll
   **nicht mehr nach KI klingen**, professionelle Hi-Fi-Soundqualität ist das Ziel.
2. User-Nachweislich getestet: "App works really good, results sound better than original."
3. UI-Anforderungen: Abbrechen-Button, Process-Button während Lauf deaktiviert (grau),
   Analyse vor Process NICHT zwingend, Versionsnummer + "by Klaus Perner (DJ LECK)",
   Donation-Button (paypal.me/klausminator), kein doppelter Autor, kein Leerraum überm Footer.
4. **User-Musik stammt von YuE2** (https://github.com/multimodal-art-projection/YuE,
   X-Codec-2.0 → Frame-Rate ~50 Hz, wird per Analyse automatisch erkannt).
5. GPU: RTX 3060 12GB – muss genutzt werden (erledigt: FP16-CUDA in neural.py).
6. App nicht automatisch starten; User will selbst starten (bat-Datei).
7. Pro Workflows: Jede Änderung muss nach GitHub gepusht werden; Version im
   pyproject/changelog/CITATION immer mit anheben (v0.1.1, v0.1.2, v0.2.0 erledigt).
8. Bugfix-Historie: Broadcast-Shape-Fehler (2,10583040 vs 2,10583041) behoben;
   Codec-frame-rate-Erklärung im README; Performance-Optimierung v0.2.0.

### OFFENE FRAGE → ERLEDIGT in v0.3.0:
"Wie können wir die Soundqualität weiter verbessern? KI Hall/Echo-Effekt reduzieren?"
→ Umgesetzt: demi_gate + echo_guard + Comb-Harmonischen + Residual-Cancellation.
  Noch offen (optional): WPE-Dereverberation, generative Band-Extension.
  User hat v0.3.x noch nicht auditiv getestet/feedbackgegeben – beim nächsten
  Mal nach Hör-Ergebnis fragen (zu trocken? residual retention anpassen).

## Wichtige Konventionen
- Keine Kommentare im Code (außer Docstrings), sparsame Antworten.
- PowerShell 5.1: KEIN `&&` (nutze `;` oder `if ($?)`), kein `head`/`tail`/`ls -la`
  → `Get-Content`, `Select-Object -First/-Last`, `Get-ChildItem`.
- Audio-Dateien (wav/mp3/flac) werden nie committet (siehe .gitignore).
- Windows-Umgebung: RTX 3060 CUDA-GPU verfügbar, Python 3.11.
