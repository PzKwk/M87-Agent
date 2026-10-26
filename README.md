# 1M SI for controlling up to 4 AI

## Unity-Builds lokal ergänzen

Die Unity-Builds sind **nicht im Repository enthalten**. Nach dem Klonen müssen
die Ordner `TestArena` und `TrainingsArena` lokal im Projektstamm (neben dieser
README) angelegt und mit den vollständigen Builds ergänzt werden. Beide Ordner
sind in `.gitignore` ausgeschlossen und werden nicht eingecheckt.

| Ordner | Inhalt | Ausführbare Datei |
| --- | --- | --- |
| `TestArena/` | Desktop-Player für sichtbare Arena-Tests | `GroundArena.exe` |
| `TrainingsArena/` | Headless-Server für das Training | `GroundArenaServer.exe` |

Die lokale Struktur soll so aussehen (weitere Builddateien sind hier ausgelassen):

```text
Agent M87/
├── README.md
├── Python/
│   └── reference/
├── TestArena/
│   ├── GroundArena.exe
│   ├── GroundArena_Data/
│   └── UnityPlayer.dll
└── TrainingsArena/
    ├── GroundArenaServer.exe
    ├── GroundArenaServer_Data/
    └── UnityPlayer.dll
```

Immer den **gesamten Buildordner** übernehmen, einschließlich `*_Data`, DLLs und
aller weiteren erzeugten Dateien und Unterordner. Die EXE allein reicht nicht.

## Builds im Unity-Projekt erstellen

Zum Erstellen wird das separate **Black-Stars-Unity-Projekt** benötigt; dieses
Repository enthält den Python-Client, nicht die Unity-Projektquellen.

1. Das Black-Stars-Projekt mit der dafür vorgesehenen Unity-Version öffnen.
   Die benötigten Windows-Buildmodule müssen installiert sein; für den
   Headless-Build zusätzlich das passende Dedicated-Server-Buildmodul.
2. Für den sichtbaren Testbuild **Black Stars → Ground Arena → Build Desktop
   Player** ausführen. Den Build unter `TestArena/GroundArena.exe` ablegen oder
   anschließend den vollständigen erzeugten Build nach `TestArena/` kopieren.
3. Für den Trainingsbuild **Black Stars → Ground Arena → Build Headless Server**
   ausführen. Den Build unter `TrainingsArena/GroundArenaServer.exe` ablegen oder
   anschließend den vollständigen erzeugten Build nach `TrainingsArena/` kopieren.
4. Prüfen, dass EXE und zugehöriger Data-Ordner wie oben benannt zusammenliegen.
   Der Buildhook legt außerdem das portable Clientpaket `GroundArenaTraining/`
   neben der EXE ab.

Die genannten Menübefehle bauen gezielt die Arena als Startszene. Ein normaler
Vollspiel-Build mit `MAIN` als erster Szene ersetzt diese Arena-Builds nicht.
Für die Nutzung fertiger Builds auf dem Trainerrechner ist kein Unity-Editor nötig.

## Build-Verbindung prüfen

Mit Python 3.9 oder neuer aus dem Projektstamm ausführen:

```powershell
python .\Python\reference\smoke_test.py --build .\TestArena\GroundArena.exe --runs "$env:TEMP\AgentM87-smoke-test" --episodes 2 --max-steps 500 --seed 42
python .\Python\reference\smoke_test.py --build .\TrainingsArena\GroundArenaServer.exe --runs "$env:TEMP\AgentM87-smoke-training" --episodes 2 --max-steps 500 --seed 42
```

Der Smoke-Test prüft die Trainingsschnittstelle, führt aber kein lernendes
Training durch. Exitcode `0` bedeutet, dass alle Episoden beendet wurden,
`1` meldet einen Fehler und `2` bedeutet, dass mindestens eine Episode nur das
lokale Schrittlimit erreicht hat; gegebenenfalls `--max-steps` erhöhen.
Logs und Ergebnisse landen in neuen Run-Unterordnern unter den angegebenen
temporären Pfaden.

Weitere Details zum Client und zur Schnittstelle stehen in
[Python/reference/README.md](Python/reference/README.md) und
[Python/reference/PROTOCOL.md](Python/reference/PROTOCOL.md).
