# Ground Arena JSON/TCP v1

Protokollkennung: `blackstars-ground-arena/1`. TCP ausschließlich auf dem lokalen
IPv4-Loopback `127.0.0.1`, eine authentifizierte Verbindung. UTF-8, genau ein
JSON-Objekt pro Zeile, Abschluss `\n`. Kein NaN/Infinity. Maximale Anfragezeile:
1 MiB ohne Zeilenende. Maximale Antwortzeile im Python-Client: 16 MiB ohne
Zeilenende, optional kleiner konfigurierbar. Beide Grenzen sind unabhängig;
eine zu große Anfrage wird vor dem Senden lokal abgewiesen.

Der Build wird so aktiviert (Groß-/Kleinschreibung beibehalten):

```text
-groundArenaTrain -groundArenaPort 0 -groundArenaEndpoint <absolute-path>
```

Port `0` wählt einen freien Port. Der Build publiziert die tatsächliche Adresse
in der Endpoint-Datei; die Datei ist kein Netzwerkbefehl:

```json
{"protocol":"blackstars-ground-arena/1","host":"127.0.0.1","port":43123,"token":"opaque-random-session-token","pid":12345}
```

Optionale Buildargumente: `-groundArenaCandidates <1..32>` (Standard 24) und
`-groundArenaRewardScale <finite-number>` (1e-12..1e12, Standard 1, Dezimalpunkt).
Sie können über `ArenaClient.launch(..., extra_args=[...])` übergeben werden.
Die Rewardskalierung verändert keine Szenariowertung oder Spielregel.

Nur `127.0.0.1` wird akzeptiert, weder DNS-Namen noch Remote-Adressen. Port muss
eine ganze Zahl 1..65535 sein, PID eine positive ganze Zahl und Token ein
nichtleerer String. Die PID identifiziert beim eigenen Start den Kindprozess;
sie ist niemals eine Berechtigung, diesen Prozess zu beenden. Endpoint-Dateien
mit Token nicht öffentlich teilen.

Jede Anfrage hat `protocol`, `id` (positive, je Verbindung steigende ganze Zahl)
und `command`. Der erste Befehl ist immer `hello` mit `token`:

```json
{"protocol":"blackstars-ground-arena/1","id":1,"command":"hello","token":"opaque-random-session-token"}
{"protocol":"blackstars-ground-arena/1","id":1,"ok":true,"data":{"interface":"custom-json-tcp","model_required":false}}
```

Das Objekt in `data` ist befehlsspezifisch; insbesondere ist der Inhalt der
Hello-Antwort kein vom Client vorausgesetztes Schema. Fehlerantwort:

```json
{"protocol":"blackstars-ground-arena/1","id":2,"ok":false,"error":{"code":"invalid_request","message":"Request rejected"}}
```

`code`/`message` im Beispiel sind illustrativ. `ok` muss ein JSON-Boolean sein;
`protocol` und `id` müssen zur Anfrage passen. Zusätzliche Antwortfelder sind
erlaubt. Doppelte JSON-Schlüssel und nicht endliche Zahlen werden abgelehnt.
Anfragen werden seriell verarbeitet, keine parallelen Calls auf einem Client.

| Command | Zusätzliche Anfragefelder | Antwortdaten |
| --- | --- | --- |
| `hello` | `token` | Handshake-Daten |
| `catalog` | keine | Szenarioslots, Paarungen, feste Armeen und Regeln |
| `reset` | `arena` 0..11, `pair_index`, `control` attacker/defender/both; optional `seed` als 32-Bit-Integer, `time_limit_seconds`, `keep_others`, `concurrency` | Frische Episode/Beobachtung, sobald echte Geometrie/Aufstellung bereit ist |
| `observe` | `episode`; optional eigene `unit_id` | Neue Beobachtung, bei Einheitenwahl deren Entscheidungskandidaten |
| `terrain` | `episode` | Gemeinsame Tilegeometrie, Begehbarkeit, Adjazenz und Modellrollen |
| `step` | `episode`, `observation_id`, `ticks` 1..200, `actions` | Beobachtung nach den angeforderten Simulationsscheiben |
| `close` | keine | Sitzung freigeben/pausieren, TCP-Verbindung schließen |

`ArenaClient.reset()` setzt standardmäßig `arena=0`, `pair_index=0`,
`control="attacker"`; ohne `seed` wird kein Seedfeld gesendet. `step()` nutzt
standardmäßig 4 Ticks. Jeder Tick entspricht 0,05 Simulationssekunden. Reset und
Step können mehrere Unityframes benötigen. Zwischen Anfragen wartet die Arena.
Die nicht kontrollierte Seite nutzt die bestehende KI. `both` kontrolliert beide
Seiten über dieselbe Verbindung.

Standardmäßig hält eine Verbindung **eine aktive Episode**. Ein gültiger neuer
Reset stoppt und entwertet sämtliche vorherigen aktiven Episoden, auch in anderen
Slots. Damit kann nach einem lokalen Schrittlimit direkt das nächste Szenario
gestartet werden. Nach bereits begonnener Ersetzung sind alte IDs auch dann
ungültig, wenn die neue Aufstellung scheitert; ein weiterer frischer Reset ist
erforderlich. Ungültige Resetfelder werden vor der Ersetzung geprüft.

Ausdrückliche Mehrfach-Arenen: `keep_others` ist ein Boolean (Standard `false`),
`concurrency` eine ganze Zahl 1..12 ohne Booleans. Beispielsweise erhält
`reset(arena=1, keep_others=True, concurrency=2)` andere Slots innerhalb des
ausdrücklichen Limits und ersetzt nur den angeforderten Slot. Jede behaltene
Episode besitzt eigene Beobachtungs-/Kandidatenreferenzen und wird einzeln durch
`step(episode, ...)` fortgesetzt. Anfragen auf einer Verbindung bleiben seriell.
Das ersetzt keine gemeinsamen Simulations-/Arbeitsbudgets. Für getrennte
Prozessumgebungen sind weiterhin mehrere Builds mit je eigenem Client und
Runordner möglich.

`reset(..., time_limit_seconds=...)` ist ausschließlich im ausgeglichenen Modus
zulässig: endliche Zahl 0..86400, keine Booleans. `0` schaltet dieses optionale
Zeitlimit aus; ohne Argument bleibt die Szenariovorgabe unverändert. Ein solches
Serverlimit führt bei Erreichen zu `truncated=true`. Das lokale Schrittlimit
eines Trainers bleibt davon getrennt. Der Server prüft die Modusberechtigung.

Aktionsbeispiele (ausschließlich bereitgestellte opake IDs verwenden):

```json
{"unit_id":"arena-Blue-0","kind":"hold"}
{"unit_id":"arena-Blue-1","kind":"move","candidate_id":17}
```

Die Namen und Nummern sind illustrativ: `unit_id` ist ein String;
`episode`, `observation_id` und `candidate_id` sind positive ganze Zahlen.
Immer die tatsächlich gelieferten Referenzen übernehmen und niemals Beispiel-IDs
in eine andere Sitzung oder Beobachtung übertragen.

Eine Bewegung trägt keine freie Weltposition. Kandidaten sind an Episode,
Beobachtung und Einheit gebunden und werden serverseitig erneut geprüft. Die
Annahme eines Aktionsobjekts garantiert keinen gültigen Bewegungsauftrag;
`action_results` enthält die tatsächlichen Ablehnungen/Ergebnisse. Die Ghost-Sperre
und gewöhnlichen Bewegungsregeln gelten weiter.

Reset-/Observe-/Step-Daten enthalten mindestens die folgenden fachlichen Felder;
weitere Felder bleiben erhalten und können für eigene Policies genutzt werden:

| Feld | Bedeutung |
| --- | --- |
| `episode`, `observation_id` | Positive ganzzahlige opake Referenzen, nicht selbst erzeugen |
| `arena`, `simulation_seconds` | Szenario und Simulationszeit |
| `coordinate_frame` | `planet_local`: Positionen relativ zum Planeten |
| `units` | Einheiten einschließlich `unit_id` (String), `model_id`, `faction`, Tile, `position`, `ghost`, `hp`, `max_hp`, `start_price`, `ghost_lock_seconds`; Rollen/Modellwerte stehen in `terrain.models` |
| `decisions` | Eigene Entscheidungen: `faction`, `unit_id`, `candidates` |
| `decisions[].candidates` | Erreichbare Punkte mit positiv ganzzahliger `candidate_id`, `tile`, `point_id`, `position`; leer bedeutet aktuell keine angebotene Bewegung |
| `scores` | Szenariowerte für `attacker` und `defender` |
| `rewards` | Lernsignale für `attacker` und `defender`, von Scores getrennt |
| `terminated`, `truncated` | Natürlicher Abschluss bzw. optionales Modus-A-Zeitlimit; beide beenden die Episode |
| `result` | `null` oder Gefechtsergebnis |
| `action_results` | Auftragsergebnisse des Steps |

Standardmäßig bis zu 24 Kandidaten (höchstens 32) für eine eigene
Entscheidungseinheit je kontrollierter Seite. `observe(..., unit_id=...)` erlaubt
die ausdrückliche Wahl einer anderen eigenen Einheit und erzeugt eine neue
Beobachtung; nach dieser Abfrage deren IDs verwenden. Terrain-/Catalog-Antworten
direkt am fertigen Build auslesen; keine festen Trainings-Tensorgrößen sind
Teil dieses Clients.

Alle gelieferten Einheiten-, Ghost-, Kandidaten- und Terrainzentrumpositionen
verwenden `planet_local`; die Antworten tragen den entsprechenden
`coordinate_frame`-Tag. Sie sind Beobachtungsdaten, keine frei sendbaren
Aktionsvektoren. Rollen und Modellstatistiken über `model_id` aus `terrain.models`
zuordnen; ein eingebettetes Rollenlabel je Einheit wird nicht vorausgesetzt.

Ein terminaler Reward wird einmal ausgegeben, ein weiteres `observe` produziert
keinen zweiten Reward. Verbindungsausfall widerruft die Trainerberechtigung,
stoppt weitere Simulation und entwertet alte IDs. Nach neuer Verbindung ist ein
frischer Reset nötig. Der Client wiederholt fehlgeschlagene Anfragen nicht.
Insbesondere darf ein Timeout-Step nicht mit alten IDs erneut gesendet werden.

`close` beendet serverseitig die Sitzung, nicht das Nutzerprogramm. Nur
`ArenaClient.launch` beendet beim lokalen Aufräumen seinen eigenen Kindprozess.
`ArenaClient.connect` besitzt und beendet keinen Buildprozess.
