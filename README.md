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
python -m gon_auswertung bericht --eingabe eingabe/beispiel.xlsx --ausgabe ausgabe --pdf   # alle Zielgruppen-Berichte
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

## Berichte je Zielgruppe (Profile)

Ein Lauf erzeugt je Profil einen eigenen Bericht (`bericht_<profil>_<JJJJ-MM>.html`, optional `.pdf`):

| Profil | Zielgruppe | Schwerpunkt |
|---|---|---|
| `geschaeftsfuehrung` | intern | volle Tiefe inkl. Objektebene |
| `gesellschafter` | Gesellschafter | Liquidität, Maßnahmen, Stresstest, eigener Anteil – ohne Objektdetails |
| `eigentuemer` | Eigentümer | Ertrag, Liquidität, Portfolio und Objektvergleich |
| `bank` | Kreditinstitute | DSCR, LTV, Debt Yield, Zinsbindung, Stresstest, Maßnahmen |

```bash
python -m gon_auswertung bericht --eingabe datei.xlsx --profil bank,gesellschafter          # Auswahl
python -m gon_auswertung bericht --eingabe datei.xlsx --gesellschafter "Gesellschafter B"   # persönlicher Bericht
python -m gon_auswertung bericht --eingabe datei.xlsx --alle-gesellschafter                 # einer je Gesellschafter
python -m gon_auswertung bericht --eingabe datei.xlsx --profil profile/beispiel_tiefgaragen.json
```

Der **persönliche Gesellschafterbericht** zeigt ausschließlich den eigenen Anteil (Quote × Kontostand, Ausschüttungen Ist/Plan,
offene Maßnahmen, Nachschuss im Stressfall, Ausschüttungsspielraum) – keine Daten anderer Gesellschafter.

### Eigene Profile für individuelle Fragestellungen

JSON-Datei anlegen (Beispiele: `profile/`). Nicht genannte Felder erbt das Profil von `erbt` (Standard `geschaeftsfuehrung`):

```json
{
  "erbt": "bank",
  "titel": "Kurzübersicht für das Finanzierungsgespräch",
  "einleitung": "Text unter der Überschrift",
  "abschnitte": ["zusammenfassung", "finanzierung", "szenarien"],
  "kacheln": ["dscr_ist", "ltv", "min_pess"],
  "ausblenden": ["t_obj", "heatmap"],
  "filter": { "nutzung": ["Tiefgarage"], "objekte": ["O01", "O02"] }
}
```

* `abschnitte`: zusammenfassung, liquiditaet, finanzierung, instandhaltung, portfolio, szenarien, gesellschafter, methodik
* `filter`: Teilportfolio. Liquidität/Kontostand betreffen die Gesamtgesellschaft und werden dann automatisch ausgeblendet.
* Gültige Kacheln und ausblendbare Elemente prüft das Programm und meldet Tippfehler.

## Inhalte des Berichts

Zusammenfassung mit Ampel-Kacheln und automatischen Kernaussagen · Liquidität · Finanzierung (Bankensicht: DSCR, LTV, Debt Yield,
Break-even, Zinsbindung) · Instandhaltung & Maßnahmen · Portfolio (Heatmap, Objekt-Ranking) · Szenarien & Risiko
(Nachschussbedarf, Ausschüttungsspielraum, verkraftbarer Mietausfall, Tornado) · Gesellschafter · Daten & Methodik
(Datenqualität, Kontoabstimmung, Glossar).

## Offene Punkte

* Mindestliquidität: bis zu einer Vorgabe gilt ein Richtwert (100.000 €) im Blatt `Parameter`; Covenants sind aktuell nicht vorgesehen.
* Eigene Excel-Vorlage: wird später geliefert, der Import wird dann darauf angepasst.
* Dunkelmodus der Grafiken (derzeit helle Diagrammflächen).
