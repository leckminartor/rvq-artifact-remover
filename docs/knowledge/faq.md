# FAQ – häufige Fragen und Antworten

Volltextsuche: `rg -i "begriff" docs/knowledge/faq.md`

## Codec / Signale

### Was bewirkt die Einstellung "Codec frame rate"?
Sie gibt die Taktrate an, mit der der RVQ-Codec Frames quantisiert
(EnCodec: 75 Hz, viele SoundStream-Varianten: 50 Hz, YuE/X-Codec-2.0: ~50 Hz).
Der Codec prägt auf der Hochband-Hüllkurve eine Amplitudenmodulation genau
bei dieser Rate ("Kammfilter-Buzz"). Die Stufe "Comb-ripple flattener"
notch't diese Linie im Envelope – seit v0.3.0 inklusive 2x/3x-Harmonischen.
Die Analyse erkennt die Rate automatisch und schlägt sie vor.

### Welche Artefakte verursacht RVQ, und wo wohnen sie?
- Statisches "eingefrorenes" Quantisierungsrauschen: metallische, zeitlich
  unveränderliche Spectral-Bins → Frozen-Unfreezer.
- Frame-Rate-AM (Kammfilter-Buzz): Envelope-Modulation bei 75/50 Hz + Harmonischen
  → Comb-Flattener.
- Musikfolgendes Rauschen ("KI-Hall", heller/blecherner Schleier): nicht statisch,
  deshalb für den Unfreezer unsichtbar → De-Metal-Adaptive-Gate (demi_gate, v0.3.0).
- Pre-Echo: Codec-Fenster leckt Energie in stille Frames vor harten Hits
  (reverse-reverb-artig) → Pre-Echo-Guard (echo_guard, v0.3.0).
- Verschmierte Transienten → Transient-Restoration (Spectral-Flux).
- Künstliches Air (inhaltlose Höhen) → Adaptiver Air-Band-Roll-Off.

### Kann DSP echten (generativen) Hall entfernen?
Nur teilweise. Hall, den das Generatormodell selbst erzeugt hat (aus
Trainingsdaten-Prior), ist kein Codec-Artefakt. Unsere Ansätze: De-Metal-Gate
(metallischer Anteil), Demucs-Residual-Cancellation (Hall-Anteil HF-gezähmt
und anteilig behalten). Für echtes Dereverberation wäre WPE oder ein
generatives Modell nötig (Roadmap).

## Einstellungen / Wirkungsweise

### Wirkt sich "Processing strength" auf alle Stufen aus?
Ja, global: Comb-Notch-Tiefe, Unfreezer-Dämpfung (strength × 9 dB), Pre-Echo-
Dämpfung (0.9 × strength), Transienten-Boost (+25 % × strength), De-Metal-Gate
(k = 0.9 × strength, max. Dämpfung 2–9 dB), Air-Shelf (strength × 6 dB).
KI-Stufe: Stem-Cleanup läuft mit strength × 0.8; höhere Strength reduziert
zusätzlich die zurückgemischte Demucs-Residual-Menge (keep × (1 − 0.5·strength)).
Praxis: Bei zu trockenen Höhen lieber Strength senken als Stufen abschalten.

### Muss man vor "Process" zwingend "Analyze artifacts" ausführen?
Nein. Die Analyse ist rein informativ (nützlich fürs Frame-Rate-Matching);
die Verarbeitung macht ihre eigene interne Analyse.

### Welche Einstellungen für YuE2-Musik?
YuE nutzt X-Codec-2.0 → Frame-Rate ~50 Hz (wird von der Analyse automatisch
erkannt und übernommen). Startwert Strength 60.

## Pipeline / Architektur

### Was macht die KI-Stufe (Demucs) genau?
htdemucs/htdemucs_ft trennt 4 Stems (drums/vocals/bass/other), die durch ein
auf sauberen Studioaufnahmen trainiertes Netz re-synthetisiert wurden – Codec-
Rauschen ohne Instrumentenzugehörigkeit verschwindet bei der Rekombination.
Jeder Stem wird danach gezielt DSP-geputzt (Bass ohne Comb, Drums mit extra
Transienten). Der Mix-minus-Stems-Residual wird HF-gezähmt und anteilig
zurückgemischt ("residual retention", Default 30 %) – Raum/Pad-Inhalte überleben.

### Warum wird die GPU (RTX 3060) genutzt/nicht genutzt?
neural.py läuft FP16 auf CUDA, wenn torch+CUDA installiert sind; Fallback FP32,
bei Fehlern FP32. Die App zeigt den erkannten Device-Status an
("GPU neural stage: CUDA - …"). DSP-Stufen sind CPU/NumPy (schnell genug).

### Ist "Analyze" schädlich oder teuer?
Nein – nur informativ, eigener Ablauf, verändert nichts.

## Verifikation

### Wie beweisen wir, dass die Pipeline wirkt?
tests/test_synthetic.py injiziert ein realistisches RVQ-Schadensmodell
(statische Envelope-Tiles 4–8 kHz + 75-Hz-AM von HF-Rauschen 10–16 kHz) und
prüft, dass Comb-Tiefe, Frozen-Energie und metallische Flachness sinken, während
Länge/Lautheit/Peak-Sicherheit erhalten bleiben. v0.3.0-Benchmark:
Comb 0.512 → 0.222 (DSP) → 0.139 (DSP+KI); Frozen 0.704 → 0.144 → 0.003.
