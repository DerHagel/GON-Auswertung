import json
from datetime import date

import pytest

from gon_auswertung.bericht import baue_html
from gon_auswertung.beispieldaten import erzeuge_beispiel
from gon_auswertung.kennzahlen import analysieren
from gon_auswertung.laden import EingabeFehler, filtere, laden
from gon_auswertung.profile import PROFILE, lade_profil


@pytest.fixture(scope="module")
def daten(tmp_path_factory):
    p = tmp_path_factory.mktemp("p") / "b.xlsx"
    erzeuge_beispiel(p, date(2026, 10, 12))
    return laden(p)


@pytest.fixture(scope="module")
def analyse(daten):
    return analysieren(daten)


@pytest.mark.parametrize("name", list(PROFILE))
def test_alle_profile_rendern(analyse, name):
    h = baue_html(analyse, lade_profil(name))
    assert "<section" in h and "Traceback" not in h


def test_abschnitte_je_zielgruppe(analyse):
    gs = baue_html(analyse, lade_profil("gesellschafter"))
    bank = baue_html(analyse, lade_profil("bank"))
    assert 'id="gesellschafter"' in gs and 'id="gesellschafter"' not in bank
    assert 'id="finanzierung"' in bank and 'id="finanzierung"' not in gs
    assert 'id="portfolio"' not in gs


def test_personenbericht_zeigt_eigenen_anteil_und_alle_quoten(analyse):
    h = baue_html(analyse, lade_profil("gesellschafter"), person="Gesellschafter B")
    assert "Ihr Anteil" in h and h.count("Ihr Anteil") == 1
    assert all(n in h for n in ("Gesellschafter A", "Gesellschafter C", "Gesellschafter D"))
    with pytest.raises(ValueError):
        baue_html(analyse, lade_profil("gesellschafter"), person="Unbekannt")


def test_quoten_anteile(analyse):
    g = analyse.gesellschafter
    assert g["Anteil_Kontostand"].sum() == pytest.approx(analyse.kpis["kontostand"].wert)
    assert g["Nachschuss_Stress"].sum() == pytest.approx(analyse.stress["nachschuss"])


def test_filter_teilportfolio(daten):
    d2 = filtere(daten, nutzung=["Tiefgarage"])
    assert set(d2.objekte["Nutzung"]) == {"Tiefgarage"} and len(d2.objekte) == 6
    assert set(d2.monat["Objekt_ID"]) <= set(d2.objekte["Objekt_ID"])
    a2 = analysieren(d2)
    h = baue_html(a2, lade_profil("eigentuemer").__class__(**{**lade_profil("eigentuemer").__dict__, "filter_nutzung": ["Tiefgarage"]}))
    assert 'id="liquiditaet"' not in h and "Kontostand allein" not in h
    with pytest.raises(EingabeFehler):
        filtere(daten, objekte=["X99"])


def test_json_profil_erbt_und_validiert(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"erbt": "bank", "titel": "Mein Bericht", "abschnitte": ["zusammenfassung"]}), encoding="utf-8")
    pr = lade_profil(str(p))
    assert pr.titel == "Mein Bericht" and pr.abschnitte == ["zusammenfassung"] and pr.kacheln == PROFILE["bank"].kacheln
    p.write_text(json.dumps({"abschnitte": ["gibtsnicht"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="ungültige"):
        lade_profil(str(p))
    p.write_text(json.dumps({"quatsch": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="unbekannte Felder"):
        lade_profil(str(p))


def test_beispielprofile_im_repo_sind_gueltig():
    for f in ("profile/beispiel_tiefgaragen.json", "profile/beispiel_bank_kurz.json"):
        lade_profil(f)
