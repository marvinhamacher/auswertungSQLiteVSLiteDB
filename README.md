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
- `--type competition --competitor TESTKÜRZEL`: passenden Test hervorheben, andere Teilnehmer anonymisieren.
- `--type normal`: Testkürzel anzeigen, falls im JSON vorhanden.
- `--enableSpecificationGroups true|false`: Hardware nach Low-/Mid-/High-End gruppieren.

## CPU-Namen

In `visualizer.py` `CPU_NAME_MAP` mit den **verifizierten** tatsächlichen CPU-Modellen befüllen. Die Windows Family/Model-Kennung wird absichtlich nicht automatisch erraten.

Beispiel:

```python
CPU_NAME_MAP = {
    "AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD": "AMD Ryzen 7 7800X3D",
}
```

## Balkenlogik

Eine Hardware-Konfiguration = eine Gruppe. Innerhalb jeder Gruppe stehen die fünf Iterationen 1–5 nebeneinander. Bei `--db both` stehen SQLite und LiteDB pro Iteration nebeneinander.
