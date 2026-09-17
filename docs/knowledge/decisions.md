# Design- und Produkt-Entscheidungen

Chronologisch, mit Begründung. Volltextsuche: `rg -i "begriff" docs/knowledge/decisions.md`

## Produkt

- **Zielbild:** Professionelle Offline-App (kein Cloud-Dienst), die RVQ-Artefakte
  aus KI-Musik entfernt. Ergebnis soll nicht mehr "nach KI klingen";
  professionelle Hi-Fi-Qualität ist das Maß.
- **Zielmaterial:** v. a. YuE2-Tracks (X-Codec-2.0, ~50 Hz Frame-Rate), aber
  generisch für EnCodec/SoundStream/DAC.
- **Philosophie:** Signal-adaptiv – jede Stufe detektiert, bevor sie eingreift;
  auf sauberem Material transparent.
- **Nicht-Mastering-Prämisse:** RVQ-Artefakte sind Codec-Level-Probleme; EQ/
  Kompression maskiert nur. Daher Analyse auf Artefaktstruktur statt Mastering.

## UI/UX

- Gradio-Desktop-App, Start über `Start RVQ Remover.bat`; die App startet NICHT
  automatisch nach Code-Änderungen (User will selbst starten).
- Cancel-Button; Process-/Analyze-Buttons während des Laufs deaktiviert.
- Analyse NICHT zwingend vor Process (eigene interne Analyse).
- UI zeigt Versionsnummer + "by Klaus Perner (DJ LECK)" + GitHub/Donation-Links
  (PayPal paypal.me/klausminator) im Footer; kein doppelter Autor, kein Leerraum
  über dem Footer.
- Nach "Analyze" wird die stärkste erkannte Frame-Rate automatisch ins Feld
  "Codec frame rate" übernommen (nur bei klarer Kamm-Linie, sonst User-Wert).
- v0.3.0: neue Checkboxes (Pre-echo guard, De-metal gate) + Slider
  "Demucs residual retention (%)" (Default 30).

## Engineering-Prozess

- Jede Code-Änderung wird committet und nach GitHub gepusht (User-Vorgabe).
- Bei jedem Release: Version in pyproject.toml, __init__.py, CITATION.cff
  gemeinsam anheben (hat sich bei v0.1.1 bewährt, als die Version vergessen wurde).
- Release-Ablauf: Commit → Push → Tag vX.Y.Z → Push Tag → GitHub Release mit
  Notes aus docs/release-notes-vX.Y.Z.md.
- Audio-Dateien werden nie committed (.gitignore); output/ bleibt lokal.
- Tests vor jedem Release: `pytest tests/ -v` muss grün sein.

## Technik

- DSP-Pipeline-Reihenfolge (v0.3.0): comb_notch → unfreeze_frozen → echo_guard →
  transient_boost → demi_gate → bandlimit; RMS-Ausgleich + Peak-Safety am Ende.
- demi_gate arbeitet in der Leistungsdomain (mag²), Minimum-Statistics-Floor
  (0.6-s-Fenster, bias 2.0), Wiener-Subtraktion mit geglätteten Gains; Ton-Schutz
  über Phasen-Lag-Test; TPDF-Dither gegen Musical Noise.
- echo_guard ist bewusst Pre-only (nicht post): Post-Smearing übernimmt
  transient_boost; Post-Dämpfung hatte Drum-Tails beschädigt (Test-Fail).
- Comb-Harmonischen mit Tiefe k/h (2x weniger tief, 3x nochmal schwächer) und
  Glättung oberhalb 3× der Frame-Rate.
- Residual-Cancellation: keep = residual_keep × (1 − 0.5·strength); Residual
  wird mit bandlimit ab hf_start×1.8 gezähmt, nicht verworfen.
- Parallelisierung: Kanäle (engine) und Stems (neural) je ThreadPoolExecutor;
  FP16 auf CUDA.

## Offene Roadmap (Priorität unklar, nach Bedarf)

1. WPE-Dereverberation als eigene Stufe (gegen echten generativen Hall).
2. Generative Band-Extension (z. B. AudioSR) statt/schonend zum Air-Roll-Off.
3. Real-time-Modus der DSP-Stufen.
4. Per-Stem-Strength-Presets in der UI.
5. Weitere Metriken: Stereo-Image-Stagnation, Modulationsrauschen.
