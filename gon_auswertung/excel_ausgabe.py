"""Excel-Auswertung (Kennzahlen, Monatsfluss, Objekte, Maßnahmen) mit nativem Kontostand-Diagramm."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .kennzahlen import Analyse


def schreibe_auswertung(a: Analyse, pfad: Path) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    kpi = pd.DataFrame([{"Kennzahl": k.titel, "Wert": k.wert, "Einheit": k.einheit, "Status": k.status or "", "Formel": k.formel, "Erklärung": k.erklaerung} for k in a.kpis.values()])
    with pd.ExcelWriter(pfad, engine="xlsxwriter", datetime_format="mm/yyyy") as xw:
        wb = xw.book
        kopf = wb.add_format({"bold": True, "bg_color": "#184f95", "font_color": "#ffffff", "border": 1})
        kpi.to_excel(xw, sheet_name="Kennzahlen", index=False)
        row = 0
        for name, e in a.ergebnisse.items():
            m = e.monat.reset_index()
            m.insert(0, "Szenario", name)
            m.to_excel(xw, sheet_name="Monatsfluss", index=False, startrow=row, header=(row == 0))
            row += len(m) + (1 if row else 1)
        a.objekt_kpis.to_excel(xw, sheet_name="Objekte", index=False)
        a.nutzung_kpis.to_excel(xw, sheet_name="Nutzungsarten", index=False)
        a.sensitivitaet.to_excel(xw, sheet_name="Sensitivitaet", index=False)
        if len(a.basis.massnahmen):
            a.basis.massnahmen.drop(columns=["Kosten_szenario"], errors="ignore").to_excel(xw, sheet_name="Massnahmen", index=False)
        pd.DataFrame(a.daten.meldungen, columns=["Stufe", "Hinweis"]).to_excel(xw, sheet_name="Datenqualitaet", index=False)
        for s in xw.sheets.values():
            s.freeze_panes(1, 0)
            s.set_column(0, 30, 16)
        xw.sheets["Kennzahlen"].set_column(0, 0, 44)
        xw.sheets["Kennzahlen"].set_column(4, 5, 70)
        # natives Diagramm Kontostand (Basis, Zeilen 2..n+1 im Blatt Monatsfluss)
        n = len(a.basis.monat)
        sp = list(a.basis.monat.reset_index().columns)
        col = sp.index("Kontostand") + 1
        ch = wb.add_chart({"type": "line"})
        ch.add_series({"name": "Kontostand (Basis)", "categories": ["Monatsfluss", 1, 1, n, 1], "values": ["Monatsfluss", 1, col, n, col],
                       "line": {"color": "#2a78d6", "width": 2.5}, "marker": {"type": "circle", "size": 7}})
        ch.set_title({"name": "Kontostand"})
        ch.set_size({"width": 760, "height": 380})
        xw.sheets["Monatsfluss"].insert_chart(n + 3 + 2 * (n + 1), 1, ch)
