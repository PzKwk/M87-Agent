# Externer Ground-Arena-Client

Dieses kopierbare Paket verbindet einen eigenständigen Python-Trainer mit einem
fertigen Black-Stars-Arena-Build. Python 3.9 oder neuer und die Standardbibliothek
genügen. Unity-Editor, Repository, API-Schlüssel und Cloudzugang werden auf der
Trainerseite nicht benötigt. Der Build muss die Trainingsschnittstelle enthalten.

Im Unity-Projekt zuerst **Black Stars → Ground Arena → Build Desktop Player**
oder **Build Headless Server** verwenden. Diese Menüs bauen gezielt die Arena als
Startszene und legen das Clientpaket daneben. Ein normaler Vollspiel-Build mit
MAIN als erster Szene ist kein Arena-Start, auch wenn die Arena zusätzlich in der
Szenenliste steht.
Das Servermenü deaktiviert für diesen Build die zusätzliche
Dedicated-Server-Ressourcenoptimierung, damit benötigte Shader-/Fontressourcen
erhalten bleiben. Anschließend stellt es die vorherige Editoroption auch im
Fehlerfall wieder her; gewöhnliche Playerbuilds verändern diese Option nicht.

Es ist eine eigene JSON/TCP-API, **kein `mlagents-learn`-Drop-in**. Dieses Paket
enthält weder Modellarchitektur noch Optimierer noch Training. Ein späterer
Gymnasium-/PyTorch-Adapter wird im eigenen Trainerprojekt entwickelt.

## Kopieren und den echten Build prüfen

Das gesamte Verzeichnis `GroundArenaTraining` kann neben den Build oder in einen
anderen Projektordner kopiert werden. Den vollständigen Unity-Build samt
`*_Data`-Ordner und Begleitdateien zusammenhalten; die EXE allein reicht nicht.
Die folgenden PowerShell-Pfade durch die tatsächlichen absoluten Pfade ersetzen:

```powershell
New-Item -ItemType Directory -Path 'C:\ArenaTrainer' -Force | Out-Null
Copy-Item -LiteralPath 'C:\ArenaBuild\GroundArenaTraining' -Destination 'C:\ArenaTrainer\GroundArenaTraining' -Recurse
python 'C:\ArenaTrainer\GroundArenaTraining\smoke_test.py' --build 'C:\ArenaBuild\BlackStars.exe' --runs 'C:\ArenaTrainer\runs' --episodes 2 --max-steps 500 --seed 42
```

Der **nicht lernende** Ablaufcheck wählt für jede angebotene Entscheidung den
ersten gültigen Kandidaten oder HOLD. Er prüft Handshake, Catalog, Reset, Step,
Observe, Terrain und Close. Er meldet `terminated`, `truncated`, Ergebnis und
Schrittlimit; bei ausschließlich HOLD gibt er eine Diagnose aus. Ein erreichtes
Schrittlimit wird nicht als Gefechtsende ausgegeben.

Exitcodes: `0` alle Episoden endeten, `1` Fehler, `2` mindestens eine Episode
erreichte nur das lokale Schrittlimit. 500 Schritte mit 4 Ticks entsprechen
höchstens 100 Simulationssekunden und können für ein Gefechtsende zu kurz sein.
Dann `--max-steps` erhöhen; der Ablauf bleibt durch dieses Limit begrenzt.
`--control both` kontrolliert beide Seiten über denselben Client.

Jeder `launch` erstellt unter `--runs` einen **neuen** UTC-Zeitstempel-/UUID-Ordner
mit `endpoint.json`, `unity.log` und beim Ablaufcheck `smoke-results.jsonl`.
Bestehende Runordner und Logs werden nicht überschrieben. Endpoint-Dateien enthalten
ein Sitzungstoken: lokal behandeln und vor dem Teilen entfernen. `unity.log`
fasst Standardausgabe und Fehlerausgabe des Builds zusammen. Der Build startet
mit seinem EXE-Verzeichnis als Arbeitsverzeichnis; das aktuelle Python-Verzeichnis
ist dafür unerheblich. Zusätzliche Unity-Argumente sind beispielsweise mit
`--build-arg=-batchmode` möglich. Die drei Trainingsstartflags bleiben reserviert.

Eine bereits laufende Instanz wird beispielsweise so gestartet und verbunden:

```powershell
& 'C:\ArenaBuild\BlackStars.exe' -groundArenaTrain -groundArenaPort 0 -groundArenaEndpoint 'C:\ArenaTrainer\manual-endpoint.json'
python 'C:\ArenaTrainer\GroundArenaTraining\smoke_test.py' --endpoint 'C:\ArenaTrainer\manual-endpoint.json' --results 'C:\ArenaTrainer\manual-results.jsonl' --max-steps 1000
```

`--results` muss eine neue Datei sein. Beim Verbinden mit einem laufenden Build
beendet `close()` nur die Trainingssitzung; das fremd gestartete Programm bleibt
offen. Bei `launch()` besitzt der Client seinen Kindprozess und beendet genau
diesen beim Schließen oder bei fehlgeschlagenem Start. Er beendet niemals einen
Prozess anhand der PID aus einer fremden Endpoint-Datei. Neue Runpfade und
PID-Abgleich verhindern die Übernahme einer alten Endpoint-Datei.

## API und eigener Trainingsablauf

`ground_arena_client.py` in das eigene Projekt kopieren oder dessen Verzeichnis
dem Python-Importpfad hinzufügen. Der Client ist synchron: ein Aufrufer pro
Verbindung. Alle Antworten bleiben Dictionaries/Listen mit ihren Originalfeldern;
zusätzliche Serverfelder werden akzeptiert. Vollständiger Vertrag:
[PROTOCOL.md](PROTOCOL.md).

```python
from ground_arena_client import ArenaClient

# Diese beiden Funktionen implementierst du im anderen Trainerprojekt.
def policy(observation):
    raise NotImplementedError("Eigene Policy aus gültigen Entscheidungskandidaten bauen")

def learn(previous, actions, current):
    raise NotImplementedError("Eigene Transition-/Reward-Verarbeitung und Optimierung")

with ArenaClient.launch(
    r"C:\ArenaBuild\BlackStars.exe", r"C:\ArenaTrainer\runs",
    timeout=120, startup_timeout=120,
) as arena:
    catalog = arena.catalog()  # Szenarios, Paarungen, Armeen und Regeln auslesen.
    for episode_index in range(100):
        observation = arena.reset(arena=0, pair_index=0, seed=episode_index,
                                  control="attacker")
        terrain = arena.terrain(observation["episode"])
        for step_index in range(5000):
            if observation["terminated"] or observation["truncated"]:
                break
            actions = policy(observation)
            current = arena.step(observation["episode"], observation["observation_id"],
                                 actions, ticks=4)
            learn(observation, actions, current)
            observation = current
        # Ein lokales Schrittlimit ist ein Trainer-Abbruch, kein Server-Gefechtsende.
        # Hier eigene Metriken/Checkpoints speichern; die nächste reset startet frisch.
```

Die eigene Policy liefert ausschließlich `{"unit_id": ..., "kind": "hold"}`
oder `{"unit_id": ..., "kind": "move", "candidate_id": ...}` mit IDs der
**aktuellen** Beobachtung. Keine Weltpositionen konstruieren. `observe(episode,
unit_id=...)` fordert die Entscheidung für eine andere eigene Einheit an; danach
die dabei frisch gelieferte `observation_id` und deren Kandidaten verwenden.
Kandidaten aus verschiedenen Beobachtungen nicht zusammenmischen.

`unit_id` ist ein String wie `arena-Blue-0`; Episoden-, Beobachtungs- und
Kandidatenkennungen sind positive ganze Zahlen. Die Werte immer aus den Antworten
übernehmen. Positionen von Einheiten, Ghosts, Kandidaten und Terrainzentren sind
`planet_local`, durch `coordinate_frame` gekennzeichnet. Modellrollen und
Statistiken über `model_id` aus `terrain.models` zuordnen; die Einheiten liefern
kein eingebettetes Rollenlabel.

Für den ausgeglichenen Modus erlaubt `reset(..., time_limit_seconds=300)` ein
optionales Serverzeitlimit. Zulässig sind endliche Zahlen 0..86400; `0` schaltet
dieses optionale Limit aus, `None` beziehungsweise Weglassen erhält die
Szenariovorgabe. Andere Modi weisen dieses Feld zurück. Serverzeitlimit
(`truncated`) und lokaler Python-Schrittdeckel sind getrennte Abbruchgründe.

Standardmäßig gibt es eine aktive Episode pro Verbindung. Der nächste gültige
`reset` stoppt und entwertet alle vorherigen Episoden, auch beim Wechsel des
Szenarios nach einem lokalen Schrittlimit. Scheitert die Ersatzaufstellung nach
Beginn der Ersetzung, bleiben die alten IDs ungültig; erneut frisch zurücksetzen.
Ungültige Resetfelder werden vorher geprüft.

Für mehrere Arenen in einem Build ausdrücklich andere Slots behalten und ein
Limit setzen, zum Beispiel `arena.reset(arena=1, keep_others=True, concurrency=2)`.
`keep_others` akzeptiert nur Booleans, `concurrency` nur ganze Zahlen 1..12.
Dieser Reset ersetzt nur den ausgewählten Slot innerhalb des angegebenen Limits.
Jede behaltene Episode mit ihrer eigenen letzten Beobachtung und
`observation_id` einzeln steppen; dieselbe Verbindung verarbeitet Anfragen seriell
und teilt weiterhin die gewöhnlichen Simulations-/Arbeitsbudgets. Für getrennte
Prozesse können mehrere Builds mit eigenen Clients und Runordnern gestartet
werden. Standard-Resets benötigen diese Optionen nicht.

Anfragen sind auf 1 MiB begrenzt und werden bei Überschreitung vor dem Senden
abgewiesen. Antworten dürfen unabhängig davon bis zu 16 MiB groß sein; eine
kleinere Antwortgrenze ist über `max_response_bytes` konfigurierbar.

`scores` sind Szenariowerte, `rewards` separate Lernsignale. Standardmäßig wird
die terminale Wertungsdifferenz einmalig als Reward ausgegeben. Terminalen Reward
aus der zurückgegebenen Beobachtung übernehmen; nachträgliches `observe` liefert
ihn nicht erneut. `terminated` **oder** `truncated` beendet die Episode. Die
eigene Normalisierung, Policy, Replay-Daten und Gewichte bleiben im Trainerordner.

`timeout=120` gilt für eine vollständige Anfrage samt asynchronem Reset/Step;
`startup_timeout=120` für den Start und Handshake. Bei langsamen Builds erhöhen.
`ArenaError` enthält `code` und `message` einer ausdrücklichen Serverablehnung;
danach ist die Verbindung noch nutzbar. `ConnectionLost` und `ProtocolError`
verwerfen die Verbindung. Nach Timeout gibt es **keinen automatischen Retry**, da
ein Step bereits ausgeführt worden sein kann. Verbindung neu herstellen und mit
`reset` eine neue Episode starten. Alte IDs niemals weiterverwenden. Ein von
`launch` gestarteter Build wird beim Verlassen des Kontextblocks beendet; für
Wiederverbindung an denselben weiterlaufenden Build dessen Prozess selbst starten
und `connect` verwenden.

## Tests ohne Unity

```powershell
python -m unittest discover -s 'C:\ArenaTrainer\GroundArenaTraining\tests' -v
```

Die Tests verwenden echte TCP-Sockets mit einem **künstlichen Protokollpeer** und
beim Starttest einen ausdrücklich nachgebildeten Prozesshandle. Sie prüfen
Framing, UTF-8/JSON-Grenzen, Fehler, fremde IDs, EOF/Timeout, Endpoints, absolute
Startargumente und Besitz-/Aufräumverhalten. Sie sind kein Nachweis eines realen
Unity-Build-Laufs. Dafür den oben beschriebenen Ablaufcheck mit dem fertigen Build
ausführen. Es werden keine Paketabhängigkeiten installiert.
