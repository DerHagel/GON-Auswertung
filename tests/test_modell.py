from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from gon_auswertung.beispieldaten import erzeuge_beispiel, schreibe_vorlage
from gon_auswertung.config import Spec
from gon_auswertung.kennzahlen import ampel, analysieren
from gon_auswertung.laden import EingabeFehler, laden
from gon_auswertung.modell import min_kontostand, simuliere


@pytest.fixture(scope="module")
def daten(tmp_path_factory):
    p = tmp_path_factory.mktemp("d") / "b.xlsx"
    erzeuge_beispiel(p, date(2026, 10, 12))
    return laden(p)


def test_zeitfenster(daten):
    assert len(daten.ist_monate) == 6 and len(daten.plan_monate) == 4
    assert len(daten.objekte) == 36


def test_cashflow_kette_und_kontostand(daten):
    g = simuliere(daten).monat
    rest = g["NOI"] - g["Kapitaldienst"] - g["Massnahmen"] - g["Ausschuettung"] + g["Nachschuss"]
    assert (g["CF_netto"] - rest).abs().max() < 1e-6
    plan = g[g["Typ"] == "Plan"]
    vorher = g.loc[daten.letzter_ist, "Kontostand"]
    for _, r in plan.iterrows():
        assert r["Kontostand"] == pytest.approx(vorher + r["CF_netto"])
        vorher = r["Kontostand"]


def test_ist_monate_unveraendert_durch_szenario(daten):
    b = simuliere(daten).monat
    s = simuliere(daten, Spec("x", leerstand=0.5, zins_pp=0.05, massnahmen_modus="max")).monat
    ist = b.index <= daten.letzter_ist
    assert (b.loc[ist, "Miete"] == s.loc[ist, "Miete"]).all()
    assert (b.loc[ist, "Kontostand"] == s.loc[ist, "Kontostand"]).all()


def test_szenarien_geordnet(daten):
    a = analysieren(daten)
    o, b, p = (min_kontostand(a.ergebnisse[n])[0] for n in ("Optimistisch", "Basis", "Pessimistisch"))
    assert o >= b >= p


def test_massnahmen_ist_nur_tatsaechliche_kosten(daten):
    e = simuliere(daten)
    m = e.massnahmen
    ist = m[m["Monat"] <= daten.letzter_ist]
    assert ist["Kosten_szenario"].sum() == pytest.approx(ist["Kosten_ist"].fillna(0).sum())


def test_ampel():
    assert ampel(1.3, 1.2, 1.0) == "gruen" and ampel(1.1, 1.2, 1.0) == "gelb" and ampel(0.9, 1.2, 1.0) == "rot"
    assert ampel(0.7, 0.6, 0.75, hoeher_besser=False) == "gelb"
    assert ampel(float("nan"), 1, 0) is None


def test_kpi_werte_plausibel(daten):
    a = analysieren(daten)
    assert 0 < a.kpis["ltv"].wert < 1
    assert a.kpis["dscr_ist"].wert == pytest.approx(
        a.basis.monat.query("Typ == 'Ist'")["NOI"].sum() / a.basis.monat.query("Typ == 'Ist'")["Kapitaldienst"].sum())
    assert a.stress["nachschuss"] >= 0 and 0 <= a.stress["leerstand_be"] <= 1
    assert len(a.kommentar) >= 5


def test_vorlage_ohne_daten_wird_abgelehnt(tmp_path):
    p = tmp_path / "v.xlsx"
    schreibe_vorlage(p)
    with pytest.raises(EingabeFehler):
        laden(p)


def test_doppelte_objekt_id(tmp_path):
    p = tmp_path / "b.xlsx"
    erzeuge_beispiel(p, date(2026, 10, 12))
    x = pd.read_excel(p, sheet_name=None)
    x["Objekte"].loc[1, "Objekt_ID"] = x["Objekte"].loc[0, "Objekt_ID"]
    with pd.ExcelWriter(p) as xw:
        for k, v in x.items():
            v.to_excel(xw, sheet_name=k, index=False)
    with pytest.raises(EingabeFehler, match="doppelte"):
        laden(p)
