"""One-off: export the user-side message log from the OpenCode session JSON
into a grep-friendly markdown file under docs/knowledge/."""

import io
import json
from datetime import datetime, timedelta, timezone

SRC = r"C:\Users\klaus\Documents\Default Project\rvq_cleaner\ai-music-rvq-artifact-removal-app.json"
OUT = r"C:\Users\klaus\Documents\Default Project\rvq_cleaner\docs\knowledge\session-user-log.md"

with io.open(SRC, encoding="utf-8-sig") as f:
    d = json.load(f)

tz = timezone(timedelta(hours=2))
lines = [
    "# Chronologischer Nutzer-Verlauf",
    "",
    "Quelle: `ai-music-rvq-artifact-removal-app.json` (exportierter OpenCode-",
    "Session-Log der ursprünglichen App-Entwicklung). Nur echte Nutzernachrichten,",
    "chronologisch. Volltextsuche: grep/Select-String über `docs/knowledge/`.",
    "",
]

for m in d["messages"]:
    info = m.get("info", {})
    if info.get("role") != "user":
        continue
    ts = info.get("time", {}).get("created")
    dt = datetime.fromtimestamp(ts / 1000, tz=tz).strftime("%Y-%m-%d %H:%M") if ts else "unbekannt"
    for p in m.get("parts", []):
        if p.get("type") == "text" and p.get("text", "").strip():
            lines.append("## " + dt)
            lines.append("")
            lines.append(p["text"].strip())
            lines.append("")

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("written:", OUT, "entries:", sum(1 for l in lines if l.startswith("## ")))
