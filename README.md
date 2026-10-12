# GON-Auswertung

Liquiditäts- und Wirtschaftlichkeitsbericht für eine Immobilien-Beteiligungsgesellschaft
(≈ 36 Objekte, Mischnutzung und Tiefgaragen). Aus einer Excel-Eingabedatei entstehen:

| Ausgabe | Zweck |
|---|---|
| `bericht_<JJJJ-MM>.html` | interaktiver Bericht (eine Datei, offline lesbar) für Gesellschafter, Eigentümer und Banken |
| `bericht_<JJJJ-MM>.pdf` | druckfähige Fassung (Option `--pdf`, benötigt Chromium) |
| `auswertung_<JJJJ-MM>.xlsx` | alle Kennzahlen, Monatsfluss je Szenario, Objekttabelle, Sensitivität |

## Schnellstart

```bash
pip install -r requirements.txt
python -m gon_auswertung beispiel                       # eingabe/beispiel.xlsx mit synthetischen Daten
python -m gon_auswertung bericht --eingabe eingabe/beispiel.xlsx --ausgabe ausgabe --pdf
python -m gon_auswertung vorlage                        # leere Eingabevorlage eingabe/vorlage.xlsx
python -m pytest tests
```

Wöchentlicher Lauf: Excel fortschreiben, Befehl `bericht` erneut ausführen (oder per Cron/Aufgabenplanung).

## Eingabedatei (Blätter)

| Blatt | Inhalt |
|---|---|
| `Objekte` | Stammdaten: ID, Name, Nutzung, Fläche, Verkehrswert, Restschuld, Zinssatz, Zinsbindung_bis |
| `Monatsdaten` | je Objekt und Monat: Typ (`Ist`/`Plan`), Soll_Miete, Miete, Fixkosten, **Zins, Tilgung (getrennt)**, Instandhaltung, Rueckstellung_Bestand |
| `Massnahmen` | außerordentliche Instandhaltung mit Spanne `Kosten_min / erwartet / max`, Termin, Status, `Kosten_ist` |
| `Konto` | Kontostand_Ende (Ist), Ausschüttung, Nachschuss |
| `Gesellschafter` | Quoten (optional) |
| `Parameter` | Schwellenwerte, Mindestliquidität, Stress-Annahmen (optional) |

Kosten immer als positive Zahlen. Das Zeitfenster ergibt sich aus den Daten (aktuell 6 Monate Ist, 4 Monate Plan).

## Rechenlogik

* NOI = Miete − Fixkosten − laufende Instandhaltung
* Cashflow vor Maßnahmen = NOI − Zins − Tilgung
* Netto-Cashflow = … − außerordentliche Maßnahmen − Ausschüttung + Nachschuss
* Kontostand: Ist laut Konto, Prognose = Fortschreibung
* Rückstellungen sind **bilanziell** und beeinflussen die Liquidität nicht; sie werden den Maßnahmen gegenübergestellt
* Szenarien (nur Plan-Monate): Basis (erwartete Kosten) · Optimistisch (Min-Kosten) · Pessimistisch (Max-Kosten, Mietausfall, Zinsaufschlag bei auslaufender Bindung)

## Bericht

Zusammenfassung mit Ampel-Kacheln und automatischen Kernaussagen · Liquidität · Finanzierung (Bankensicht: DSCR, LTV, Debt Yield,
Break-even, Zinsbindung) · Instandhaltung & Maßnahmen · Portfolio (Heatmap, Objekt-Ranking) · Szenarien & Risiko
(Nachschussbedarf, Ausschüttungsspielraum, verkraftbarer Mietausfall, Tornado) · Daten & Methodik (Datenqualität, Kontoabstimmung, Glossar).

## Offene Punkte

* Mindestliquidität und Covenants: bis zur Vorgabe gilt ein Richtwert (100.000 €) im Blatt `Parameter`.
* Dunkelmodus der Grafiken (derzeit helle Diagrammflächen).
