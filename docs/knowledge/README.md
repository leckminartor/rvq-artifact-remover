# Wissensdatenbank (Knowledge Base)

Volltext-durchsuchbare Ablage für Projektwissen, das über Sessions hinweg
bestehen soll. Ergänzt `AGENTS.md` (Kurzfassung) um das Detailwissen.

## Dateien

| Datei | Inhalt |
|---|---|
| `faq.md` | Nutzerfragen + Antworten (Codecs, Einstellungen, Wirkungsweise) |
| `decisions.md` | Design-/Produkt-Entscheidungen mit Begründung |
| `troubleshooting.md` | Bekannte Bugs + Fixes + Heuristiken |
| `session-user-log.md` | Chronologischer Rohverlauf aller Nutzernachrichten (auto-generiert) |

## Suche

- ripgrep: `rg -i "Suchbegriff" docs/knowledge/`
- PowerShell: `Select-String -Path docs\knowledge\*.md -Pattern "Begriff"`
- Nachtfall-sicher: Suchbegriffe klein schreiben, `-i` nutzen.

## Pflege

- Nach jeder Session mit neuen Entscheidungen/Bugfixes: hier ergänzen.
- `session-user-log.md` wird von `scripts/export_user_log.py` regeneriert
  (liest die Session-JSON im Repo-Root neu ein).
- AGENTS.md bleibt die Kurzfassung; Details gehören hierher, nicht in AGENTS.md.
