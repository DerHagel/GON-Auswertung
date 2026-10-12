"""Kommandozeile: vorlage | beispiel | bericht"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .bericht import baue_html, erzeuge_pdf
from .beispieldaten import erzeuge_beispiel, schreibe_vorlage
from .excel_ausgabe import schreibe_auswertung
from .kennzahlen import analysieren
from .laden import EingabeFehler, laden


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
    a = analysieren(daten)
    out = Path(args.ausgabe)
    out.mkdir(parents=True, exist_ok=True)
    stand = f"{daten.letzter_ist:%Y-%m}"
    h = out / f"bericht_{stand}.html"
    h.write_text(baue_html(a), encoding="utf-8")
    schreibe_auswertung(a, out / f"auswertung_{stand}.xlsx")
    print(f"HTML:  {h}\nExcel: {out / f'auswertung_{stand}.xlsx'}")
    if args.pdf:
        p = out / f"bericht_{stand}.pdf"
        print(f"PDF:   {p}" if erzeuge_pdf(h, p) else "PDF nicht erzeugt (kein Chromium gefunden).")
    for stufe, t in daten.meldungen:
        print(f"[{stufe}] {t}")
    return 0
