# Benchmark Visualizer

Gruppierte Balkenansicht für die SQLite/LiteDB-Benchmark-JSONs.

## Start

```bash
python -m pip install -r requirements.txt
python visualizer.py
```

Oder direkt mit mehreren JSON-Dateien:

```bash
python visualizer.py *.json --metric queryrate --db both --threads 8 --operation select
```

## Modi

- `--type anonym`: Hardware anzeigen, Testkürzel ausblenden.
- `--type competition --competitor TESTKÜRZEL`: passenden Test hervorheben, andere Teilnehmer anonymisieren. Das Testkürzel steht zusätzlich direkt unter der jeweiligen Balkengruppe.
- `--type normal`: Testkürzel anzeigen.
- `--enableSpecificationGroups true|false`: Kompatibilitätsalias für die Hardware-Level-Gruppierung.

## Darstellung

- **Hardware-Level gruppieren**: sortiert und trennt die Hardware in High-End, Mid-Range und Low-End.
- **Mittelwertlinie**: zeichnet eine horizontale Linie über den Mittelwert aller aktuell sichtbaren Messwerte.
- **Farbmodus Hardware**: identische Hardware-Konfigurationen erhalten dieselbe Farbe.
- **Farbmodus Akribisch**: jedes geladene Benchmark-Dataset erhält eine eigene Farbe.
- **SQLite/LiteDB gleiche Farbe**: SQLite und LiteDB innerhalb derselben Benchmark-Gruppe werden gleich eingefärbt. Wenn deaktiviert, bekommen die beiden Datenbanken getrennte Farbtöne.

Die Legende erklärt nur noch Datenbank, Mittelwert und Konkurrenz-Markierung und listet nicht mehr jedes einzelne Hardware-System auf.

## CPU-Namen

Die CPU-Namen werden in `hardwareService.py` über verifizierte Kombinationen aus Windows Family/Model, Kernen, Threads und beobachteter Maximalfrequenz zugeordnet.

## Testkürzel

Wenn ein JSON kein explizites `test_code`-Feld besitzt, wird das übergeordnete Verzeichnis als Testkürzel verwendet. Das passt zum aktuellen `dbresults/<testkürzel>/result_....json`-Export.
