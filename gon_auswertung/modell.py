"""Rechenmodell: Objekt-Monats-Cashflow, Gesellschaftsebene, Kontostand-Fortschreibung.

Vorzeichenkonvention: alle Kosten positiv; Cashflow = Einnahmen - Ausgaben.
Rückstellungen sind (vorerst) rein bilanziell und beeinflussen den Kontostand NICHT.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Spec
from .laden import Daten


@dataclass
class Ergebnis:
    spec: Spec
    objekt_monat: pd.DataFrame
    monat: pd.DataFrame        # Gesellschaft x Monat (Index = Monat)
    massnahmen: pd.DataFrame   # im Szenario wirksame Maßnahmen-Kosten je Zeile


def _massnahmen_kosten(d: Daten, spec: Spec) -> pd.DataFrame:
    m = d.massnahmen.copy()
    if m.empty:
        m["Kosten_szenario"] = pd.Series(dtype=float)
        return m
    ist = m["Monat"] <= d.letzter_ist
    spalte = {"min": "Kosten_min", "erwartet": "Kosten_erwartet", "max": "Kosten_max"}[spec.massnahmen_modus]
    kosten = m[spalte] * spec.massnahmen_faktor
    # Vergangenheit: nur tatsächlich angefallene Kosten
    kosten = np.where(ist, m["Kosten_ist"].fillna(0.0), kosten)
    m["Kosten_szenario"] = kosten
    # entfallene Maßnahmen und in der Zukunft bereits abgeschlossene zählen nicht (nicht mehr offen)
    m.loc[m["Status"] == "entfallen", "Kosten_szenario"] = 0.0
    m.loc[(m["Status"] == "abgeschlossen") & ~ist, "Kosten_szenario"] = 0.0
    return m


def simuliere(d: Daten, spec: Spec | None = None) -> Ergebnis:
    spec = spec or Spec("Basis")
    om = d.monat.merge(d.objekte[["Objekt_ID", "Restschuld", "Zinsbindung_bis"]], on="Objekt_ID", how="left")
    plan = om["Typ"] == "Plan"

    # Miete / Fixkosten: nur im Prognosezeitraum verändert
    om["Miete_s"] = np.where(plan, om["Miete"] * (1 - spec.leerstand) * spec.miete_faktor, om["Miete"])
    om["Fixkosten_s"] = np.where(plan, om["Fixkosten"] * spec.fixk_faktor, om["Fixkosten"])
    # Zinsstress: nur Objekte, deren Zinsbindung im Prognosezeitraum ausläuft (ab dem Folgemonat)
    abgelaufen = plan & om["Zinsbindung_bis"].notna() & (om["Monat"] > om["Zinsbindung_bis"])
    om["Zins_s"] = om["Zins"] + np.where(abgelaufen, om["Restschuld"].fillna(0) * spec.zins_pp / 12, 0.0)

    mk = _massnahmen_kosten(d, spec)
    if len(mk):
        agg = mk.groupby(["Objekt_ID", "Monat"], as_index=False)["Kosten_szenario"].sum().rename(columns={"Kosten_szenario": "Massnahmen"})
        om = om.merge(agg, on=["Objekt_ID", "Monat"], how="left")
    else:
        om["Massnahmen"] = 0.0
    om["Massnahmen"] = om["Massnahmen"].fillna(0.0)

    om["Kapitaldienst"] = om["Zins_s"] + om["Tilgung"]
    om["NOI"] = om["Miete_s"] - om["Fixkosten_s"] - om["Instandhaltung"]
    om["CF_vor_Massnahmen"] = om["NOI"] - om["Kapitaldienst"]
    om["CF_objekt"] = om["CF_vor_Massnahmen"] - om["Massnahmen"]

    # --- Gesellschaft
    g = om.groupby("Monat").agg(
        Typ=("Typ", "first"),
        Soll_Miete=("Soll_Miete", "sum"),
        Miete=("Miete_s", "sum"),
        Fixkosten=("Fixkosten_s", "sum"),
        Zins=("Zins_s", "sum"),
        Tilgung=("Tilgung", "sum"),
        Instandhaltung=("Instandhaltung", "sum"),
        Massnahmen=("Massnahmen", "sum"),
        Rueckstellung_Bestand=("Rueckstellung_Bestand", "sum"),
    )
    g["Kapitaldienst"] = g["Zins"] + g["Tilgung"]
    g["NOI"] = g["Miete"] - g["Fixkosten"] - g["Instandhaltung"]
    g["CF_vor_Massnahmen"] = g["NOI"] - g["Kapitaldienst"]
    k = d.konto.set_index("Monat")
    g["Ausschuettung"] = k["Ausschuettung"].reindex(g.index).fillna(0.0)
    g["Nachschuss"] = k["Nachschuss"].reindex(g.index).fillna(0.0)
    g["CF_netto"] = g["CF_vor_Massnahmen"] - g["Massnahmen"] - g["Ausschuettung"] + g["Nachschuss"]

    # Kontostand: Ist laut Bank/Buchhaltung, Prognose = Fortschreibung
    ist_ks = k["Kontostand_Ende"].reindex(g.index)
    ks, vorher = [], np.nan
    for monat, row in g.iterrows():
        if row["Typ"] == "Ist" and pd.notna(ist_ks[monat]):
            wert = float(ist_ks[monat])
        elif pd.isna(vorher):
            wert = np.nan
        else:
            wert = vorher + row["CF_netto"]
        ks.append(wert)
        vorher = wert
    g["Kontostand"] = ks
    # Abstimmung: berechneter Cashflow vs. Kontoveränderung (nur Ist-Monate)
    delta = g["Kontostand"].diff()
    g["Abstimmung_Differenz"] = np.where(g["Typ"] == "Ist", delta - g["CF_netto"], np.nan)
    g.loc[g.index[0], "Abstimmung_Differenz"] = np.nan
    return Ergebnis(spec, om, g, mk)


def min_kontostand(e: Ergebnis) -> tuple[float, pd.Timestamp]:
    plan = e.monat[e.monat["Typ"] == "Plan"]
    quelle = plan if len(plan) else e.monat
    return float(quelle["Kontostand"].min()), quelle["Kontostand"].idxmin()
