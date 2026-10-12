"""Erzeugt die Excel-Vorlage und eine realistische Beispieldatei mit synthetischen Daten (36 Objekte)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .config import PARAMETER_DEFAULTS
from .laden import SPALTEN

NUTZUNGEN = ["Mischnutzung", "Wohnen", "Gewerbe", "Tiefgarage"]

ANLEITUNG = [
    "Eingabedatei für die GON-Auswertung (wöchentlich fortschreiben)",
    "",
    "Blatt Objekte: Stammdaten je Objekt (einmalig, bei Änderungen anpassen). Restschuld = aktueller Stand.",
    "Blatt Monatsdaten: eine Zeile je Objekt und Monat. Typ = Ist (abgeschlossene Monate) oder Plan (Prognose).",
    "   Alle Kosten als POSITIVE Zahlen. Kapitaldienst getrennt in Zins und Tilgung erfassen (nicht in Fixkosten).",
    "   Soll_Miete = Miete bei Vollvermietung (optional, ermöglicht Auslastung / Leerstand).",
    "   Rueckstellung_Bestand = bilanzieller Bestand je Objekt zum Monatsende (optional).",
    "Blatt Massnahmen: außerordentliche Instandhaltung mit Kostenspanne (min / erwartet / max).",
    "   Status: geplant | beauftragt | abgeschlossen | entfallen. Kosten_ist nach Abschluss eintragen.",
    "Blatt Konto: Kontostand_Ende (Ist-Monate, laut Kontoauszug), Ausschüttungen und Nachschüsse (auch geplant).",
    "Blatt Gesellschafter: Name und Beteiligungsquote (optional).",
    "Blatt Parameter: Schwellenwerte und Szenario-Annahmen (optional, sonst Richtwerte).",
    "",
    "Aufruf:  python -m gon_auswertung bericht --eingabe <datei.xlsx> --ausgabe <ordner>",
]


def schreibe_excel(pfad: Path, blaetter: dict[str, pd.DataFrame]) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(pfad, engine="xlsxwriter", datetime_format="yyyy-mm-dd", date_format="yyyy-mm-dd") as xw:
        wb = xw.book
        kopf = wb.add_format({"bold": True, "bg_color": "#184f95", "font_color": "#ffffff", "border": 1, "text_wrap": True, "valign": "top"})
        text = wb.add_format({"text_wrap": True, "valign": "top"})
        ws = wb.add_worksheet("Anleitung")
        xw.sheets["Anleitung"] = ws
        ws.set_column(0, 0, 130)
        for i, z in enumerate(ANLEITUNG):
            ws.write(i, 0, z, wb.add_format({"bold": True, "font_size": 14}) if i == 0 else text)
        for name, df in blaetter.items():
            df.to_excel(xw, sheet_name=name, index=False)
            s = xw.sheets[name]
            for j, c in enumerate(df.columns):
                s.write(0, j, c, kopf)
                s.set_column(j, j, max(12, len(c) + 3))
            s.freeze_panes(1, 0)
            s.autofilter(0, 0, max(len(df), 1), len(df.columns) - 1)
        if "Monatsdaten" in blaetter:
            xw.sheets["Monatsdaten"].data_validation(1, 2, 20000, 2, {"validate": "list", "source": ["Ist", "Plan"]})
        if "Massnahmen" in blaetter:
            xw.sheets["Massnahmen"].data_validation(1, 8, 2000, 8, {"validate": "list", "source": ["geplant", "beauftragt", "abgeschlossen", "entfallen"]})
        if "Objekte" in blaetter:
            xw.sheets["Objekte"].data_validation(1, 2, 2000, 2, {"validate": "list", "source": NUTZUNGEN})


def parameter_blatt() -> pd.DataFrame:
    return pd.DataFrame([{"Schluessel": k, "Wert": v[0], "Beschreibung": v[1]} for k, v in PARAMETER_DEFAULTS.items()])


def schreibe_vorlage(pfad: Path) -> None:
    leer = {b: pd.DataFrame(columns=cols) for b, cols in SPALTEN.items()}
    leer["Parameter"] = parameter_blatt()
    schreibe_excel(pfad, leer)


# ----------------------------------------------------------------------------------------------
def erzeuge_beispiel(pfad: Path, stichtag: date | None = None, seed: int = 42) -> None:
    rng = np.random.default_rng(seed)
    stichtag = stichtag or date.today()
    aktuell = pd.Timestamp(stichtag).to_period("M").to_timestamp()
    monate = [aktuell + pd.DateOffset(months=i) for i in range(-6, 4)]      # 6 Ist + 4 Plan (aktueller Monat = Plan)
    ist = monate[:6]

    # --- Objekte
    nutzungen = ["Mischnutzung"] * 20 + ["Gewerbe"] * 6 + ["Wohnen"] * 4 + ["Tiefgarage"] * 6
    strassen = ["Hauptstr.", "Bahnhofstr.", "Gartenweg", "Marktplatz", "Ringstr.", "Lindenallee", "Schulstr.", "Kirchgasse", "Industriestr.", "Parkstr."]
    objs = []
    for i, nu in enumerate(nutzungen, start=1):
        if nu == "Tiefgarage":
            fl, qm_miete, faktor = rng.uniform(700, 2200), rng.uniform(5.5, 7.5), rng.uniform(13, 16)
        elif nu == "Gewerbe":
            fl, qm_miete, faktor = rng.uniform(800, 3200), rng.uniform(10.5, 15.5), rng.uniform(12, 16)
        elif nu == "Wohnen":
            fl, qm_miete, faktor = rng.uniform(600, 1800), rng.uniform(9.5, 12.5), rng.uniform(17, 22)
        else:
            fl, qm_miete, faktor = rng.uniform(500, 2800), rng.uniform(10, 13.5), rng.uniform(15, 20)
        voll = fl * qm_miete
        vw = voll * 12 * faktor
        ltv = rng.uniform(0.45, 0.66)
        zins = rng.uniform(0.022, 0.046)
        bindung = aktuell + pd.DateOffset(months=int(rng.integers(2, 120)))
        objs.append(dict(Objekt_ID=f"O{i:02d}", Name=f"{rng.choice(strassen)} {int(rng.integers(1, 90))} ({nu})", Nutzung=nu,
                         Flaeche_qm=round(fl), Verkehrswert=round(vw, -3), Restschuld=round(vw * ltv, -3), Zinssatz=round(zins, 4),
                         Zinsbindung_bis=bindung.to_period("M").to_timestamp("M").date(), _voll=voll))
    objekte = pd.DataFrame(objs)
    # drei Darlehen laufen im Prognosezeitraum aus der Zinsbindung (Anschlussfinanzierung)
    for idx, mon_plus in ((2, 1), (11, 2), (27, 3)):
        objekte.loc[idx, "Zinsbindung_bis"] = (aktuell + pd.DateOffset(months=mon_plus)).to_period("M").to_timestamp("M").date()
    # zwei Problemobjekte: hohe Leerstände / hoher Kapitaldienst
    objekte.loc[7, "Restschuld"] = round(objekte.loc[7, "Verkehrswert"] * 0.7, -3)
    objekte.loc[21, "Restschuld"] = round(objekte.loc[21, "Verkehrswert"] * 0.68, -3)

    # --- Monatsdaten
    zeilen = []
    for _, o in objekte.iterrows():
        auslast = rng.uniform(0.94, 1.0)
        if o.name in (7, 14):
            auslast = rng.uniform(0.80, 0.86)
        fix_q = rng.uniform(0.20, 0.30)
        ih_q = rng.uniform(0.05, 0.10)
        rueck = rng.uniform(0.3, 1.2) * o._voll * 12 * 0.1
        tilg = rng.uniform(0.015, 0.025)
        for m in monate:
            plan = m not in ist
            soll = o._voll * (1 + 0.0015 * (monate.index(m)))      # leichte Indexierung
            miete = soll * np.clip(auslast + rng.normal(0, 0.012), 0.5, 1.0)
            fix = soll * fix_q * rng.normal(1, 0.03)
            ih = soll * ih_q * (rng.normal(1, 0.25) if not plan else 1.0)
            zins_m = o.Restschuld * o.Zinssatz / 12
            tilg_m = o.Restschuld * tilg / 12
            rueck += soll * 0.015
            zeilen.append(dict(Monat=m.date(), Objekt_ID=o.Objekt_ID, Typ="Plan" if plan else "Ist", Soll_Miete=round(soll, 2),
                               Miete=round(miete, 2), Fixkosten=round(fix, 2), Zins=round(zins_m, 2), Tilgung=round(tilg_m, 2),
                               Instandhaltung=round(max(ih, 0), 2), Rueckstellung_Bestand=round(rueck, 2)))
    monat = pd.DataFrame(zeilen)

    # --- Maßnahmen
    def mon(i):
        return monate[i].date()
    mass = [
        ("M01", "O03", "Dachsanierung Teilbereich", mon(7), 110_000, 140_000, 190_000, None, "beauftragt"),
        ("M02", "O12", "Aufzugsmodernisierung", mon(6), 55_000, 70_000, 95_000, None, "geplant"),
        ("M03", "O18", "Heizungsumstellung", mon(8), 65_000, 85_000, 120_000, None, "geplant"),
        ("M04", "O25", "Fassadenanstrich", mon(9), 40_000, 55_000, 75_000, None, "geplant"),
        ("M05", "O31", "TG-Betonsanierung", mon(7), 50_000, 70_000, 110_000, None, "geplant"),
        ("M06", "O08", "Brandschutznachrüstung", mon(6), 18_000, 25_000, 35_000, None, "beauftragt"),
        ("M07", "O22", "Fenstertausch Teilbereich", mon(3), 38_000, 45_000, 60_000, 47_300, "abgeschlossen"),
        ("M08", "O15", "Flachdachabdichtung", mon(1), 22_000, 28_000, 36_000, 26_800, "abgeschlossen"),
        ("M09", "O05", "Leitungserneuerung Keller", mon(8), 30_000, 42_000, 60_000, None, "geplant"),
    ]
    massn = pd.DataFrame(mass, columns=SPALTEN["Massnahmen"])

    # --- Konto: Ist-Kontostand durch Rückrechnung konsistent zum Cashflow (kleine Differenz in einem Monat)
    cf = {}
    for m in monate:
        z = monat[monat["Monat"] == m.date()]
        mk = massn[(massn["Monat"] == m.date())]
        kost = mk["Kosten_ist"].fillna(0).sum() if m in ist else 0.0
        cf[m] = z["Miete"].sum() - z["Fixkosten"].sum() - z["Zins"].sum() - z["Tilgung"].sum() - z["Instandhaltung"].sum() - kost
    ausschuettung = {monate[8]: 80_000.0}
    ist_ausschuettung = {2: 100_000.0, 5: 80_000.0}
    ks, stand = [], 260_000.0
    for i, m in enumerate(monate):
        if m in ist:
            stand += cf[m] + (-4_500 if i == 3 else 0) - ist_ausschuettung.get(i, 0.0)
            ks.append(round(stand, 2))
        else:
            ks.append(None)
    konto = pd.DataFrame({"Monat": [m.date() for m in monate], "Kontostand_Ende": ks,
                          "Ausschuettung": [ausschuettung.get(m, 0.0) + ist_ausschuettung.get(i, 0.0) for i, m in enumerate(monate)], "Nachschuss": 0.0})
    gesell = pd.DataFrame({"Name": ["Gesellschafter A", "Gesellschafter B", "Gesellschafter C", "Gesellschafter D"], "Quote": [0.40, 0.30, 0.20, 0.10]})

    objekte = objekte.drop(columns="_voll")
    schreibe_excel(pfad, {"Objekte": objekte, "Monatsdaten": monat, "Massnahmen": massn, "Konto": konto,
                          "Gesellschafter": gesell, "Parameter": parameter_blatt()})
