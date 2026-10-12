"""Berichtsprofile: je Zielgruppe Abschnitte, Kennzahlen und Detailtiefe festlegen.

Eigene Profile lassen sich als JSON-Datei ablegen (Beispiele im Ordner `profile/`), z. B. für
individuelle Fragestellungen oder Teilportfolios. Nicht angegebene Felder erben vom Basisprofil
(`erbt`, Standard: geschaeftsfuehrung).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

ABSCHNITTE = ["zusammenfassung", "liquiditaet", "finanzierung", "instandhaltung", "portfolio", "szenarien", "gesellschafter", "methodik"]
ABSCHNITT_TITEL = {
    "zusammenfassung": "Zusammenfassung", "liquiditaet": "Liquidität", "finanzierung": "Finanzierung (Bank)",
    "instandhaltung": "Instandhaltung & Maßnahmen", "portfolio": "Portfolio", "szenarien": "Szenarien & Risiko",
    "gesellschafter": "Gesellschafter", "methodik": "Daten & Methodik",
}
KACHELN = ["kontostand", "min_basis", "min_pess", "puffer", "dscr_ist", "dscr_plan", "auslastung", "ltv", "debt_yield", "noi_rendite",
           "cf_rendite", "break_even", "kd_quote", "fix_quote", "noi_marge", "rueck_deckung", "kassen_deckung", "massn_offen", "rueckstellung", "ih_qm", "cf_ist"]
# Ausblendbare Elemente: Grafiken und Tabellen
ELEMENTE = ["kontostand", "cashflow", "wasserfall_ist", "wasserfall_plan", "kapitaldienst", "massnahmen", "deckung", "heatmap", "dscr_objekte",
            "auslastung_be", "nutzung", "tornado", "zinsbindung", "t_monat", "t_massn", "t_obj", "t_nutz", "t_szen", "t_abst", "t_gloss", "t_ges"]
KOMMENTAR_THEMEN = ["liquiditaet", "finanzierung", "portfolio", "massnahmen"]


@dataclass
class Profil:
    name: str
    titel: str = "Liquiditäts- und Wirtschaftlichkeitsbericht"
    zielgruppe: str = ""
    einleitung: str = ""
    abschnitte: list[str] = field(default_factory=lambda: list(ABSCHNITTE))
    kacheln: list[str] = field(default_factory=lambda: ["kontostand", "min_basis", "min_pess", "puffer", "dscr_ist", "auslastung", "ltv", "rueck_deckung", "kassen_deckung", "massn_offen"])
    fin_kacheln: list[str] = field(default_factory=lambda: ["dscr_ist", "dscr_plan", "kd_quote", "ltv", "debt_yield", "noi_rendite", "cf_rendite", "break_even"])
    ausblenden: list[str] = field(default_factory=list)
    kommentar_themen: list[str] = field(default_factory=lambda: list(KOMMENTAR_THEMEN))
    filter_nutzung: list[str] = field(default_factory=list)
    filter_objekte: list[str] = field(default_factory=list)
    erbt: str = ""

    @property
    def gefiltert(self) -> bool:
        return bool(self.filter_nutzung or self.filter_objekte)


BASIS = Profil("geschaeftsfuehrung", titel="Liquiditäts- und Wirtschaftlichkeitsbericht – Geschäftsführung",
               zielgruppe="Geschäftsführung / interne Steuerung: volle Tiefe inkl. Objektebene.",
               kacheln=["kontostand", "min_basis", "min_pess", "puffer", "dscr_ist", "auslastung", "ltv", "rueck_deckung", "kassen_deckung", "massn_offen"])

PROFILE: dict[str, Profil] = {
    "geschaeftsfuehrung": BASIS,
    "gesellschafter": Profil(
        "gesellschafter", titel="Gesellschafterbericht", zielgruppe="Gesellschafter: Liquidität, Maßnahmen, Risiken und eigener Anteil – ohne Objektdetails.",
        einleitung="Dieser Bericht zeigt, wie es um die Zahlungsfähigkeit der Gesellschaft steht, welche größeren Instandhaltungen anstehen und was das für Ausschüttungen und mögliche Nachschüsse bedeutet.",
        abschnitte=["zusammenfassung", "liquiditaet", "instandhaltung", "szenarien", "gesellschafter", "methodik"],
        kacheln=["kontostand", "min_basis", "min_pess", "puffer", "massn_offen", "dscr_ist"],
        ausblenden=["t_monat", "heatmap", "dscr_objekte", "t_obj", "t_nutz", "t_abst", "wasserfall_ist", "wasserfall_plan"],
        kommentar_themen=["liquiditaet", "massnahmen", "finanzierung"]),
    "eigentuemer": Profil(
        "eigentuemer", titel="Eigentümerbericht", zielgruppe="Eigentümer: Ertragslage, Liquidität und Zustand des Portfolios inkl. Objektvergleich.",
        abschnitte=["zusammenfassung", "liquiditaet", "instandhaltung", "portfolio", "szenarien", "methodik"],
        kacheln=["kontostand", "min_basis", "min_pess", "dscr_ist", "auslastung", "noi_rendite", "cf_rendite", "ltv", "massn_offen", "rueck_deckung"],
        ausblenden=["t_abst"]),
    "bank": Profil(
        "bank", titel="Finanzierungsbericht für Kreditinstitute", zielgruppe="Banken: Kapitaldienstfähigkeit, Sicherheiten, Zinsbindung, Stresstest.",
        abschnitte=["zusammenfassung", "finanzierung", "portfolio", "instandhaltung", "szenarien", "methodik"],
        kacheln=["dscr_ist", "dscr_plan", "ltv", "debt_yield", "break_even", "auslastung", "kontostand", "min_pess"],
        fin_kacheln=["dscr_ist", "dscr_plan", "kd_quote", "ltv", "debt_yield", "noi_rendite", "break_even", "noi_marge"],
        ausblenden=["cashflow", "wasserfall_ist", "wasserfall_plan", "t_monat"],
        kommentar_themen=["finanzierung", "portfolio", "liquiditaet", "massnahmen"]),
}


def _pruefe(p: Profil) -> None:
    for liste, erlaubt, was in ((p.abschnitte, ABSCHNITTE, "abschnitte"), (p.kacheln, KACHELN, "kacheln"), (p.fin_kacheln, KACHELN, "fin_kacheln"),
                                (p.ausblenden, ELEMENTE, "ausblenden"), (p.kommentar_themen, KOMMENTAR_THEMEN, "kommentar_themen")):
        falsch = [x for x in liste if x not in erlaubt]
        if falsch:
            raise ValueError(f"Profil '{p.name}': ungültige Werte in '{was}': {falsch}. Erlaubt: {erlaubt}")


def lade_profil(name_oder_pfad: str) -> Profil:
    """Eingebautes Profil (Name) oder JSON-Datei laden. Felder der JSON-Datei überschreiben das Basisprofil."""
    if name_oder_pfad in PROFILE:
        return PROFILE[name_oder_pfad]
    pfad = Path(name_oder_pfad)
    if not pfad.exists():
        raise ValueError(f"Profil '{name_oder_pfad}' unbekannt (eingebaut: {', '.join(PROFILE)}; oder Pfad zu einer JSON-Datei).")
    roh = json.loads(pfad.read_text(encoding="utf-8"))
    basis = PROFILE.get(roh.get("erbt", "geschaeftsfuehrung"))
    if basis is None:
        raise ValueError(f"{pfad}: 'erbt' verweist auf unbekanntes Profil '{roh['erbt']}'.")
    erlaubt = {f.name for f in fields(Profil)}
    # Kurzschreibweise für den Filter in der JSON-Datei
    filt = roh.pop("filter", {}) or {}
    roh["filter_nutzung"] = filt.get("nutzung", roh.get("filter_nutzung", []))
    roh["filter_objekte"] = filt.get("objekte", roh.get("filter_objekte", []))
    unbekannt = set(roh) - erlaubt
    if unbekannt:
        raise ValueError(f"{pfad}: unbekannte Felder {sorted(unbekannt)}")
    roh.setdefault("name", pfad.stem)
    p = replace(basis, **roh)
    _pruefe(p)
    return p
