"""Einlesen und Plausibilisieren der Excel-Eingabedatei."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import PARAMETER_DEFAULTS

SPALTEN = {
    "Objekte": ["Objekt_ID", "Name", "Nutzung", "Flaeche_qm", "Verkehrswert", "Restschuld", "Zinssatz", "Zinsbindung_bis"],
    "Monatsdaten": ["Monat", "Objekt_ID", "Typ", "Soll_Miete", "Miete", "Fixkosten", "Zins", "Tilgung", "Instandhaltung", "Rueckstellung_Bestand"],
    "Massnahmen": ["Massnahme_ID", "Objekt_ID", "Bezeichnung", "Monat", "Kosten_min", "Kosten_erwartet", "Kosten_max", "Kosten_ist", "Status"],
    "Konto": ["Monat", "Kontostand_Ende", "Ausschuettung", "Nachschuss"],
    "Gesellschafter": ["Name", "Quote"],
    "Parameter": ["Schluessel", "Wert", "Beschreibung"],
}
PFLICHT_BLAETTER = ["Objekte", "Monatsdaten", "Konto"]
STATI = {"geplant", "beauftragt", "abgeschlossen", "entfallen"}
GELDSPALTEN = ["Soll_Miete", "Miete", "Fixkosten", "Zins", "Tilgung", "Instandhaltung"]


class EingabeFehler(ValueError):
    """Eingabedatei ist so fehlerhaft, dass keine Auswertung möglich ist."""


@dataclass
class Daten:
    objekte: pd.DataFrame
    monat: pd.DataFrame            # Objekt x Monat
    massnahmen: pd.DataFrame
    konto: pd.DataFrame
    gesellschafter: pd.DataFrame
    params: dict[str, float]
    letzter_ist: pd.Timestamp
    monate: list[pd.Timestamp]
    meldungen: list[tuple[str, str]] = field(default_factory=list)   # (Stufe, Text)

    @property
    def ist_monate(self) -> list[pd.Timestamp]:
        return [m for m in self.monate if m <= self.letzter_ist]

    @property
    def plan_monate(self) -> list[pd.Timestamp]:
        return [m for m in self.monate if m > self.letzter_ist]


def _monat(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.to_period("M").dt.to_timestamp()


def laden(pfad: str | Path) -> Daten:
    pfad = Path(pfad)
    if not pfad.exists():
        raise EingabeFehler(f"Datei nicht gefunden: {pfad}")
    xl = pd.ExcelFile(pfad)
    meld: list[tuple[str, str]] = []

    for blatt in PFLICHT_BLAETTER:
        if blatt not in xl.sheet_names:
            raise EingabeFehler(f"Pflichtblatt '{blatt}' fehlt.")

    def lese(blatt: str, pflicht: bool = True) -> pd.DataFrame:
        if blatt not in xl.sheet_names:
            return pd.DataFrame(columns=SPALTEN[blatt])
        df = xl.parse(blatt)
        df = df.dropna(how="all")
        fehlt = [c for c in SPALTEN[blatt] if c not in df.columns]
        # optionale Spalten
        optional = {"Soll_Miete", "Rueckstellung_Bestand", "Kosten_ist", "Kosten_min", "Kosten_max"}
        kritisch = [c for c in fehlt if c not in optional]
        if kritisch:
            raise EingabeFehler(f"Blatt '{blatt}': Spalten fehlen: {', '.join(kritisch)}")
        for c in fehlt:
            df[c] = pd.NA
        return df[SPALTEN[blatt]].copy()

    objekte = lese("Objekte")
    monat = lese("Monatsdaten")
    massn = lese("Massnahmen")
    konto = lese("Konto")
    gesell = lese("Gesellschafter")
    par = lese("Parameter")

    # --- Objekte
    objekte["Objekt_ID"] = objekte["Objekt_ID"].astype(str).str.strip()
    if objekte["Objekt_ID"].duplicated().any():
        raise EingabeFehler("Objekte: doppelte Objekt_ID: " + ", ".join(objekte.loc[objekte["Objekt_ID"].duplicated(), "Objekt_ID"]))
    for c in ["Flaeche_qm", "Verkehrswert", "Restschuld", "Zinssatz"]:
        objekte[c] = pd.to_numeric(objekte[c], errors="coerce")
        if objekte[c].isna().any():
            meld.append(("warn", f"Objekte: Spalte {c} hat fehlende Werte bei {', '.join(objekte.loc[objekte[c].isna(), 'Objekt_ID'])} – abhängige Kennzahlen entfallen dort."))
    objekte["Zinsbindung_bis"] = pd.to_datetime(objekte["Zinsbindung_bis"], errors="coerce")

    # --- Monatsdaten
    monat["Objekt_ID"] = monat["Objekt_ID"].astype(str).str.strip()
    monat["Monat"] = _monat(monat["Monat"])
    monat["Typ"] = monat["Typ"].astype(str).str.strip().str.capitalize()
    if not monat["Typ"].isin(["Ist", "Plan"]).all():
        raise EingabeFehler("Monatsdaten: Spalte Typ darf nur 'Ist' oder 'Plan' enthalten.")
    for c in GELDSPALTEN + ["Rueckstellung_Bestand"]:
        monat[c] = pd.to_numeric(monat[c], errors="coerce")
    monat["Soll_Miete"] = monat["Soll_Miete"].fillna(monat["Miete"])
    unbekannt = set(monat["Objekt_ID"]) - set(objekte["Objekt_ID"])
    if unbekannt:
        raise EingabeFehler("Monatsdaten: unbekannte Objekt_ID: " + ", ".join(sorted(unbekannt)))
    if monat.duplicated(["Monat", "Objekt_ID"]).any():
        raise EingabeFehler("Monatsdaten: doppelte Kombination Monat/Objekt_ID.")
    leer = monat[GELDSPALTEN[1:]].isna().any(axis=1)
    if leer.any():
        meld.append(("warn", f"Monatsdaten: {int(leer.sum())} Zeilen mit fehlenden Beträgen (werden als 0 gewertet)."))
        monat[GELDSPALTEN] = monat[GELDSPALTEN].fillna(0.0)
    if (monat[GELDSPALTEN] < 0).any().any():
        meld.append(("warn", "Monatsdaten: negative Beträge gefunden – Kosten bitte als positive Zahlen erfassen."))
    if monat["Typ"].eq("Ist").sum() == 0:
        raise EingabeFehler("Monatsdaten enthalten keine Ist-Monate.")
    letzter_ist = monat.loc[monat["Typ"] == "Ist", "Monat"].max()
    wrong = monat[(monat["Typ"] == "Plan") & (monat["Monat"] <= letzter_ist)]
    if len(wrong):
        meld.append(("warn", "Monatsdaten: Plan-Zeilen liegen vor/in dem letzten Ist-Monat – sie werden als Ist behandelt."))
        monat.loc[monat["Monat"] <= letzter_ist, "Typ"] = "Ist"
    monate = sorted(monat["Monat"].unique())
    # Vollständigkeit Objekt x Monat
    soll = len(objekte) * len(monate)
    if len(monat) < soll:
        meld.append(("warn", f"Monatsdaten: {soll - len(monat)} Objekt-Monat-Kombinationen fehlen (z. B. neues/verkauftes Objekt)."))

    # --- Maßnahmen
    if len(massn):
        massn["Objekt_ID"] = massn["Objekt_ID"].astype(str).str.strip()
        massn["Monat"] = _monat(massn["Monat"])
        massn["Status"] = massn["Status"].astype(str).str.strip().str.lower().replace({"nan": "geplant"})
        bad = ~massn["Status"].isin(STATI)
        if bad.any():
            raise EingabeFehler(f"Maßnahmen: unzulässiger Status {sorted(set(massn.loc[bad, 'Status']))}; erlaubt: {sorted(STATI)}")
        for c in ["Kosten_min", "Kosten_erwartet", "Kosten_max", "Kosten_ist"]:
            massn[c] = pd.to_numeric(massn[c], errors="coerce")
        massn["Kosten_min"] = massn["Kosten_min"].fillna(massn["Kosten_erwartet"])
        massn["Kosten_max"] = massn["Kosten_max"].fillna(massn["Kosten_erwartet"])
        if massn["Kosten_erwartet"].isna().any():
            raise EingabeFehler("Maßnahmen: Kosten_erwartet fehlt bei " + ", ".join(massn.loc[massn["Kosten_erwartet"].isna(), "Massnahme_ID"].astype(str)))
        unb = set(massn["Objekt_ID"]) - set(objekte["Objekt_ID"])
        if unb:
            raise EingabeFehler("Maßnahmen: unbekannte Objekt_ID: " + ", ".join(sorted(unb)))
        überfällig = massn[(massn["Monat"] <= letzter_ist) & massn["Status"].isin(["geplant", "beauftragt"])]
        if len(überfällig):
            meld.append(("warn", "Maßnahmen mit Termin in der Vergangenheit, aber nicht abgeschlossen: " + ", ".join(überfällig["Massnahme_ID"].astype(str)) + " – bitte Status/Termin pflegen."))
        ohne_ist = massn[(massn["Status"] == "abgeschlossen") & massn["Kosten_ist"].isna()]
        if len(ohne_ist):
            meld.append(("warn", "Abgeschlossene Maßnahmen ohne Kosten_ist (werden mit 0 € gewertet): " + ", ".join(ohne_ist["Massnahme_ID"].astype(str))))
    else:
        massn = pd.DataFrame(columns=SPALTEN["Massnahmen"])
        meld.append(("info", "Keine Maßnahmen erfasst."))

    # --- Konto
    konto["Monat"] = _monat(konto["Monat"])
    for c in ["Kontostand_Ende", "Ausschuettung", "Nachschuss"]:
        konto[c] = pd.to_numeric(konto[c], errors="coerce")
    konto[["Ausschuettung", "Nachschuss"]] = konto[["Ausschuettung", "Nachschuss"]].fillna(0.0)
    if konto.loc[konto["Monat"] == letzter_ist, "Kontostand_Ende"].isna().all():
        raise EingabeFehler(f"Konto: Kontostand_Ende für den letzten Ist-Monat ({letzter_ist:%m/%Y}) fehlt.")

    # --- Gesellschafter
    if len(gesell):
        gesell["Quote"] = pd.to_numeric(gesell["Quote"], errors="coerce")
        if abs(gesell["Quote"].sum() - 1) > 0.001 and abs(gesell["Quote"].sum() - 100) > 0.1:
            meld.append(("warn", f"Gesellschafter: Quoten summieren sich auf {gesell['Quote'].sum():g} (erwartet 1 bzw. 100 %)."))
        if gesell["Quote"].sum() > 1.5:
            gesell["Quote"] = gesell["Quote"] / 100
    else:
        meld.append(("info", "Keine Gesellschafter erfasst – Nachschuss-/Ausschüttungsverteilung entfällt."))

    # --- Parameter
    params = {k: v[0] for k, v in PARAMETER_DEFAULTS.items()}
    if len(par):
        for _, r in par.iterrows():
            k = str(r["Schluessel"]).strip()
            if k in params and pd.notna(r["Wert"]):
                params[k] = float(r["Wert"])
            elif k not in params:
                meld.append(("warn", f"Parameter: unbekannter Schlüssel '{k}' ignoriert."))
    else:
        meld.append(("info", "Parameter-Blatt leer: Standardwerte (Richtwerte) werden verwendet."))
    if params["mindestliquiditaet"] == PARAMETER_DEFAULTS["mindestliquiditaet"][0]:
        meld.append(("info", "Mindestliquidität entspricht dem Standard-Richtwert – bitte durch Vorgabe aus Gesellschaftsvertrag/Bank ersetzen, sobald vorhanden."))

    return Daten(objekte, monat, massn, konto, gesell, params, letzter_ist, monate, meld)
