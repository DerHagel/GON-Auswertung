"""Kommandozeile: vorlage | beispiel | bericht"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from .bericht import baue_html, erzeuge_pdf
from .beispieldaten import erzeuge_beispiel, schreibe_vorlage
from .excel_ausgabe import schreibe_auswertung
from .kennzahlen import analysieren
from .laden import EingabeFehler, filtere, laden
from .profile import PROFILE, lade_profil


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")).strip("-")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gon_auswertung", description="Liquiditäts- und Wirtschaftlichkeitsbericht")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("vorlage", help="leere Excel-Eingabevorlage erzeugen")
    v.add_argument("--ausgabe", default="eingabe/vorlage.xlsx")
    b = sub.add_parser("beispiel", help="Beispieldatei mit synthetischen Daten erzeugen")
    b.add_argument("--ausgabe", default="eingabe/beispiel.xlsx")
    b.add_argument("--stichtag", default=None, help="YYYY-MM-DD (Standard: heute)")
    r = sub.add_parser("bericht", help="Auswertung erzeugen (HTML, Excel, optional PDF)")
    r.add_argument("--eingabe", required=True)
    r.add_argument("--ausgabe", default="ausgabe")
    r.add_argument("--pdf", action="store_true", help="zusätzlich PDF erzeugen (benötigt Chromium)")
    r.add_argument("--profil", default="alle", help="Profile, kommagetrennt: geschaeftsfuehrung,gesellschafter,eigentuemer,bank oder Pfad(e) zu JSON-Dateien (Standard: alle eingebauten)")
    r.add_argument("--gesellschafter", action="append", default=[], help="persönlicher Gesellschafterbericht für diesen Namen (mehrfach möglich)")
    r.add_argument("--alle-gesellschafter", action="store_true", help="persönlichen Bericht für jeden Gesellschafter erzeugen")
    args = ap.parse_args(argv)

    if args.cmd == "vorlage":
        schreibe_vorlage(Path(args.ausgabe))
        print(f"Vorlage geschrieben: {args.ausgabe}")
        return 0
    if args.cmd == "beispiel":
        st = date.fromisoformat(args.stichtag) if args.stichtag else None
        erzeuge_beispiel(Path(args.ausgabe), st)
        print(f"Beispieldatei geschrieben: {args.ausgabe}")
        return 0
    try:
        daten = laden(args.eingabe)
    except EingabeFehler as e:
        print(f"FEHLER in der Eingabedatei: {e}", file=sys.stderr)
        return 2
    try:
        namen = list(PROFILE) if args.profil == "alle" else [x.strip() for x in args.profil.split(",") if x.strip()]
        profile = [lade_profil(n) for n in namen]
    except ValueError as e:
        print(f"FEHLER im Profil: {e}", file=sys.stderr)
        return 2
    personen = list(args.gesellschafter)
    if args.alle_gesellschafter:
        personen += [n for n in daten.gesellschafter["Name"] if n not in personen]
    a = analysieren(daten)
    out = Path(args.ausgabe)
    out.mkdir(parents=True, exist_ok=True)
    stand = f"{daten.letzter_ist:%Y-%m}"
    schreibe_auswertung(a, out / f"auswertung_{stand}.xlsx")
    print(f"Excel: {out / f'auswertung_{stand}.xlsx'}")

    auftraege = [(p, None) for p in profile]
    if personen:
        auftraege += [(lade_profil("gesellschafter"), n) for n in personen]
    for prof, person in auftraege:
        try:
            if prof.gefiltert:
                a_p = analysieren(filtere(daten, prof.filter_nutzung, prof.filter_objekte))
            else:
                a_p = a
            teil = f"{prof.name}_{_slug(person)}" if person else prof.name
            h = out / f"bericht_{teil}_{stand}.html"
            h.write_text(baue_html(a_p, prof, person), encoding="utf-8")
        except (ValueError, EingabeFehler) as e:
            print(f"FEHLER ({prof.name}): {e}", file=sys.stderr)
            return 2
        print(f"HTML:  {h}")
        if args.pdf:
            pdf = h.with_suffix(".pdf")
            print(f"PDF:   {pdf}" if erzeuge_pdf(h, pdf) else "PDF nicht erzeugt (kein Chromium gefunden).")
    for stufe, t in daten.meldungen:
        print(f"[{stufe}] {t}")
    return 0
