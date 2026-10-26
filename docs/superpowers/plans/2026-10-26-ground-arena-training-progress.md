# Fortschritt: 2026-10-26-ground-arena-training.md

## Freigegebener Umfang

Nutzerauftrag: Schritte 1 und 2 der letzten Chatantwort ausführen, vor Schritt 3 stoppen.
Das bedeutet: KI.md vollständig lesen; vorhandenes Python-Kit nach Python/reference kopieren und Kopien prüfen. Kein Arena-Start, kein Smoke-Testlauf, keine Installation, kein Training und keine API-Aufrufe.

## Lesestand

- Quelle: C:/Users/lrt71/Black Stars - The M87 Conflict/Markdown/KI.md
- Länge: 560176 UTF-16-Zeichen (PowerShell .NET string), zuvor 6394 Zeilen / 567570 Bytes ermittelt.
- SHA-256 vor/zu Beginn der abschnittsweisen Lektüre: B6F75B0863D35AF3AA5D7CD9541F0E970969C3EBCA4B57B43F5B6BACD57DCB2F
- Vollständig und ohne Tool-Ausgabekürzung gelesen: Zeichen [0, 560176), in 22 Abschnitten mit jeweils 25000 Zeichen und einem Schlussabschnitt mit 10176 Zeichen. Eine gekürzte Ausgabe bei Offset 450000 wurde vollständig wiederholt.
- SHA-256 nach der vollständigen Lektüre erneut geprüft: identisch zum Anfangshash.

## Bisherige Befunde

- Datierte neuere Regeln ersetzen ältere: insbesondere Sold 5/20/25 Prozent sowie Fußinfanterie-Immunität gegen BREAKDOWN/Ghost-Reset.
- Gemeinsame Autorität, bezahlte Aktionen, Konten, Navigation, Kampf und Arbeitsbudgets bleiben maßgeblich.
- Historische Legacy-/Modell-/Generalstabspfade nicht mit aktueller MAIN- oder Arena-Anbindung gleichsetzen.
- Arena-Training ist eine eigene lokale Schnittstelle; synthetische Tests sind kein nativer Unity-Nachweis.
- Der aktuelle MAIN-TypeSafe-Pfad unterstützt die deterministische KI mit begrenzten Bodenabsichten. Die spätere Ergänzung vom 23.10. ersetzt die ältere Passwortanforderung; Hostfreigabe, Sitzungsgrant und normale Spielregeln bleiben nötig. Das belegt keine entsprechende Anbindung im vorhandenen Arena-Build.
- Nutzergrenze bleibt verbindlich: Training ausschließlich deterministisch ohne TypeSafe/API; Jev-Unterstützung nur im getrennten späteren Benchmark.

## Umsetzung

- Sechs unveränderte Dateien nach `Python/reference/` kopiert: `.gitignore`, `ground_arena_client.py`, `smoke_test.py`, `README.md`, `PROTOCOL.md`, `tests/test_client.py`.
- Alle sechs SHA-256-Paare stimmen überein; Quellhashes wurden unmittelbar vor und nach der Kopie geprüft. Keine Caches, Geheimnisse oder Spielabhängigkeiten kopiert.
- Nachweis: `docs/validation/2026-10-26-preflight/kit-copy-verification.json`.
- Kein Arena-/Dienststart, keine Installation, keine Tests und keine Provideraufrufe ausgeführt. Spielprojekt unverändert; `Models/` bleibt leer.
- Umsetzungshinweis: Hier wird nur Dokumentation gelesen und ein unverändertes Kit kopiert. Kein neuer Implementierungscode, keine Testentwicklung, kein Git-Setup und keine Spielprojektänderung erforderlich.
- Freigegebene Schritte 1 und 2 abgeschlossen. Auf ausdrücklichen Nutzerwunsch vor Schritt 3 (Arena starten) gestoppt. Der echte Unity-End-to-End-Nachweis und die übrigen Planaufgaben bleiben offen.
