# Python-Agent außerhalb des Unity-Projekts

Stand: 26.10.2026. Die Unity-seitige Trainingsschnittstelle und der portable Python-
Client sind implementiert. Lernalgorithmus und Modell werden anschließend im anderen
Projektordner entwickelt. Native Unity-/Build-End-to-End-Prüfung bleibt offen;
Nachweise stehen im [Prüfbericht](../docs/validation/2026-10-26-ground-arena-training/README.md).

## Build und Übergabe

In Unity **Black Stars → Ground Arena → Build Desktop Player** oder
**Build Headless Server** verwenden. Diese Menüs bauen gezielt die Arena als
Startszene. Der Server benötigt das passende installierte Unity-Buildmodul.
Ein gewöhnlicher Vollspiel-Build startet dagegen weiterhin MAIN.

Der Buildhook legt **GroundArenaTraining/** neben die EXE: Client, Smoke-Test,
Protokollbeschreibung und Python-Tests. Den vollständigen Build mit Data-Ordner und
Begleitdateien im späteren Projektordner zusammenhalten; die EXE allein genügt nicht.
Eigene Agentdateien werden durch den Buildhook nicht entfernt; nur bekannte
generierte Kitdateien ersetzt. Auf Trainerseite reichen Python 3.9+ und die
Standardbibliothek für den Client, ohne Unity-Editor, Cloud oder API-Schlüssel.

Der Arena-Serverbuild erhält die benötigten Material-/Schriftressourcen, indem er
die zusätzliche Server-Assetentfernung für seinen Buildvorgang deaktiviert und die
vorherige Editoroption anschließend auch bei Fehlern wiederherstellt. Die Option
ist im Projekt aktiviert und entfernt laut
[Unity-Dokumentation](https://docs.unity.com/en-us/engine/6000.0/manual/platform-specific/dedicated-server/get-started/optimizations)
unter anderem Shader. Es gibt dadurch keine dauerhafte Projektoptionsänderung.

## Start im anderen Ordner

Die vollständige kopierbare Anleitung mit eigener Trainingsschleife liegt unter
[Tools/GroundArenaTraining/README.md](../Tools/GroundArenaTraining/README.md).
Beispiel für den ausdrücklich nicht lernenden Verbindungs-/Ablaufcheck:

```powershell
python 'C:\MeinTrainer\GroundArenaTraining\smoke_test.py' --build 'C:\MeinTrainer\Build\GroundArena.exe' --runs 'C:\MeinTrainer\runs' --max-steps 500
```

Der Check wählt angebotene Kandidaten oder HOLD. Ein erreichtes lokales Schrittlimit
(Exit 2) ist kein behauptetes Gefechtsende. Der Client erstellt einen neuen Runordner
mit atomarer Endpointdatei, Unity-Log und Ergebnissen. Absolute Pfade und eigener
Kindprozessbesitz erlauben den Start aus beliebigem Arbeitsverzeichnis.

```python
from ground_arena_client import ArenaClient

with ArenaClient.launch(
    r"C:\MeinTrainer\Build\GroundArena.exe", r"C:\MeinTrainer\runs"
) as arena:
    catalog = arena.catalog()
    observation = arena.reset(arena=1, pair_index=0, seed=87, control="attacker")
    # Eigene Policy, Beobachtungskodierung und Optimierung im Trainerprojekt.
    # arena.step(episode, observation_id, actions, ticks=4)
```

## Vertrag und Berechtigungen

`-groundArenaTrain` schaltet ausdrücklich einen eigenen **Trainer**-Controller
frei, gebunden an eine authentifizierte lokale Verbindung. Ein fertiges Modell ist
dafür nicht nötig. Menschliche Seiten sind in diesem Betrieb ausgeschlossen.
Lokale SI-Inferenz für Spiele mit Menschen bleibt eine eigene spätere Integration;
das bloße Ablegen einer Modelldatei aktiviert sie nicht automatisch.

`catalog`, `reset`, `observe`, `terrain`, `step` und `close` steuern den Build.
Die Arena wartet zwischen Anfragen. Pro Unityframe läuft höchstens eine angeforderte
gemeinsame Simulationsscheibe von 0,05 Sekunden; gemeinsame AI-Budgets bleiben erhalten.
Beobachtungen enthalten alle Bodeneinheiten, Preis-/HP-/Ghostzustände und bis zu
32 gültige Kandidaten für eine eigene Entscheidungseinheit je Trainerseite.
`observe(..., unit_id=...)` wählt eine andere eigene Einheit. Positionen sind
`planet_local`; Modellrollen stehen unter `terrain.models`.

Aktionen sind HOLD oder MOVE auf eine aktuelle opake Kandidatenkennung. Freie
Weltvektoren sind keine Aktion. Fehlende manuelle Punktsets ergänzt der Trainerbetrieb
durch sechs feste lokale Stützstellen pro vorhandenem Quellmesh, auf dessen echter
Geometrie gesampelt. Sie gelten auch auf Plains und werden vor Ausgabe/Annahme mit
Unterstützung, Erreichbarkeit, Bewegungstyp, Körperabständen und Ghost-Sperre geprüft.
Manuelle Sets haben Vorrang. Generische Bewegungspunkte behaupten keinen manuell
abgenommenen Deckungs-/Höhenvorteil.

Ein gewöhnlicher Reset beendet alle bisherigen Trainer-Episoden, auch nach einem
eigenen lokalen Trainingsabbruch. `keep_others=True, concurrency=2` hält ausdrücklich
weitere Slots bis zur Grenze 1..12. Jede Episode besitzt eigene Konten/Uhren und wird
mit ihrer eigenen Kennung geschritten; andere laufen nicht ungefragt weiter.
Alternativ mehrere Buildprozesse starten. Alte Episoden-/Beobachtungs-/Kandidatenkennungen
werden nach Ersatz, Fehler oder Disconnect abgewiesen. Unterbrochene Schritte liefern
einen Fehler statt übersprungene Ticks als Erfolg auszugeben. Timeouts werden nicht
automatisch wiederholt; nach Verbindungswechsel ist ein frischer Reset nötig.

`scores` bleiben die Szenariowerte; `rewards` sind separat deren einmalige terminale
Differenz, geteilt durch den konfigurierbaren RewardScale (Standard 1, 1e-12..1e12).
Python kann eigene Lernsignale/Normalisierung aus den Beobachtungen berechnen.
`terminated` und `truncated` unterscheiden natürliche Enden und das optionale Modus-A-
Zeitlimit (`time_limit_seconds`, 0..86400; 0 = aus). Modus B bleibt bei 900 Sekunden.
Ergebnisse liegen unter `training-results.jsonl` neben der Endpointdatei.

## Umfang und offene Abnahme

Es ist eine eigene versionierte TCP/JSON-API auf 127.0.0.1, kein eingebauter
ML-Agents-/`mlagents-learn`-Adapter. PyTorch, Gymnasium und ML-Agents werden nicht
automatisch installiert; keine Netzarchitektur, Tensorgröße oder Parameterzahl ist
vorgegeben. Eigene Agenten-/Trainingsänderungen benötigen keinen Unity-Rebuild,
solange sie den [Protokollvertrag](../Tools/GroundArenaTraining/PROTOCOL.md) verwenden.
Neue Spielaktionen oder bisher nicht übertragene Zustandsfelder erfordern dagegen
eine Unity-Protokollerweiterung und einen neuen Build.

Transport-/Testpeer-Prüfungen ersetzen keinen echten Buildlauf. Native Geometrie,
sichtbare Kämpfe, Headless-Buildstart, Desktop-/XR-Interaktion und W5120-Performance
sind gesondert zu prüfen; die dokumentierte Unity-Lizenzsperre wurde nicht erneut versucht.
