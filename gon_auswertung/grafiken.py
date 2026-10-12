"""Plotly-Grafiken. Farben aus der validierten Referenzpalette (siehe dataviz-Skill), Ampel = Status-Palette.

Regeln: eine Achse je Grafik (kein Doppel-Y), Farbe folgt der Größe (nicht dem Rang), Status nie nur über Farbe.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .kennzahlen import GELB, GRUEN, ROT, Analyse
from .modell import min_kontostand

# Kategorische Reihenfolge (Slots 1-5) -> feste Zuordnung je Größe
C = {
    "Miete": "#2a78d6", "Fixkosten": "#6250d6", "Zins": "#eb6834", "Tilgung": "#eda100",
    "Instandhaltung": "#1baf7a", "Massnahmen": "#e87ba4", "Ausschuettung": "#898781", "Nachschuss": "#0ca30c",
}
SZ = {"Basis": "#2a78d6", "Optimistisch": "#1baf7a", "Pessimistisch": "#eb6834"}
STATUS = {GRUEN: "#0ca30c", GELB: "#fab219", ROT: "#d03b3b"}
TINTE, TINTE2, GRID, BASE = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
LABEL = {"Miete": "Mieteinnahmen", "Fixkosten": "Feste Kosten (ohne Kapitaldienst)", "Zins": "Zinsen", "Tilgung": "Tilgung",
         "Instandhaltung": "Laufende Instandhaltung", "Massnahmen": "Außerordentliche Instandhaltung",
         "Ausschuettung": "Ausschüttung", "Nachschuss": "Nachschuss"}


def eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", ".")


def _layout(fig: go.Figure, hoehe: int = 420, legende: bool = True) -> go.Figure:
    fig.update_layout(
        height=hoehe, margin=dict(l=70, r=24, t=36 if legende else 16, b=48),
        paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb",
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", size=13, color=TINTE2),
        separators=",.", hoverlabel=dict(bgcolor="#fcfcfb", font_color=TINTE, bordercolor=BASE),
        legend=dict(orientation="h", y=1.12, x=0, font=dict(color=TINTE2)) if legende else dict(),
        showlegend=legende,
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=BASE, zerolinecolor=BASE, tickfont=dict(color="#898781"))
    fig.update_yaxes(gridcolor=GRID, linecolor=BASE, zerolinecolor=BASE, tickfont=dict(color="#898781"))
    return fig


def dz(x, n=2) -> str:
    return f"{x:.{n}f}".replace(".", ",")


def _mon(ts) -> str:
    return f"{ts:%m/%Y}"


def _grenze(fig: go.Figure, a: Analyse, row=None, col=None) -> None:
    """Trennlinie Ist | Prognose."""
    x = a.daten.letzter_ist + pd.Timedelta(days=15)
    kw = {} if row is None else dict(row=row, col=col)
    fig.add_vline(x=x, line=dict(color=BASE, width=1.5, dash="dot"), **kw)
    fig.add_annotation(x=x, y=1.0, yref="paper", text="Prognose →", showarrow=False, xanchor="left", yanchor="bottom",
                       font=dict(size=12, color="#898781"))


# ----------------------------------------------------------------------------------------------
def fig_kontostand(a: Analyse) -> go.Figure:
    d, p = a.daten, a.daten.params
    fig = go.Figure()
    b = a.ergebnisse["Basis"].monat
    start = d.letzter_ist
    ist = b[b.index <= start]
    # Korridor
    o = a.ergebnisse["Optimistisch"].monat
    s = a.ergebnisse["Pessimistisch"].monat
    plan_idx = [start] + d.plan_monate
    fig.add_trace(go.Scatter(x=plan_idx, y=o.loc[plan_idx, "Kontostand"], mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=plan_idx, y=s.loc[plan_idx, "Kontostand"], mode="lines", line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(42,120,214,0.14)", name="Korridor optimistisch – pessimistisch", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=ist.index, y=ist["Kontostand"], mode="lines+markers", name="Ist", line=dict(color=SZ["Basis"], width=2.5),
                             marker=dict(size=8, line=dict(color="#fcfcfb", width=2)), hovertemplate="%{x|%m/%Y}: %{y:,.0f} €<extra>Ist</extra>"))
    for name, e in a.ergebnisse.items():
        z = e.monat.loc[plan_idx]
        fig.add_trace(go.Scatter(x=z.index, y=z["Kontostand"], mode="lines+markers", name=f"Prognose {name}",
                                 line=dict(color=SZ[name], width=2.5 if name == "Basis" else 1.8, dash="dash"),
                                 marker=dict(size=8 if name == "Basis" else 6, line=dict(color="#fcfcfb", width=2)),
                                 hovertemplate="%{x|%m/%Y}: %{y:,.0f} €<extra>" + name + "</extra>"))
    fig.add_hline(y=p["mindestliquiditaet"], line=dict(color=STATUS[ROT], width=1.5, dash="dot"),
                  annotation_text=f"Mindestliquidität {eur(p['mindestliquiditaet'])}", annotation_position="bottom right",
                  annotation_font=dict(color=TINTE2, size=12))
    for nm in ("Basis", "Pessimistisch"):
        mn, wann = min_kontostand(a.ergebnisse[nm])
        fig.add_annotation(x=wann, y=mn, text=f"Tief ({nm}): {eur(mn)}", showarrow=True, arrowhead=0, ay=34 if nm == "Pessimistisch" else -34,
                           font=dict(size=12, color=TINTE), arrowcolor=BASE, bgcolor="#fcfcfb")
    _grenze(fig, a)
    fig.update_yaxes(title_text="Kontostand", tickformat=",.0f", ticksuffix=" €")
    fig.update_xaxes(tickformat="%m/%Y", dtick="M1")
    return _layout(fig, 460)


def fig_cashflow(a: Analyse) -> go.Figure:
    g = a.basis.monat
    fig = go.Figure()
    for k in ["Fixkosten", "Zins", "Tilgung", "Instandhaltung", "Massnahmen"]:
        fig.add_trace(go.Bar(x=g.index, y=g[k], name=LABEL[k], marker_color=C[k], marker_line=dict(color="#fcfcfb", width=2),
                             hovertemplate="%{x|%m/%Y}: %{y:,.0f} €<extra>" + LABEL[k] + "</extra>"))
    fig.add_trace(go.Scatter(x=g.index, y=g["Miete"], name=LABEL["Miete"], mode="lines+markers", line=dict(color=C["Miete"], width=3),
                             marker=dict(size=8, line=dict(color="#fcfcfb", width=2)), hovertemplate="%{x|%m/%Y}: %{y:,.0f} €<extra>Mieteinnahmen</extra>"))
    fig.update_layout(barmode="stack")
    _grenze(fig, a)
    fig.update_yaxes(title_text="€ pro Monat", tickformat=",.0f")
    fig.update_xaxes(tickformat="%m/%Y", dtick="M1")
    return _layout(fig, 440)


def fig_wasserfall(a: Analyse, monate: list[pd.Timestamp], titel: str) -> go.Figure:
    g = a.basis.monat.loc[monate]
    s = g[["Miete", "Fixkosten", "Instandhaltung", "Zins", "Tilgung", "Massnahmen", "Ausschuettung", "Nachschuss"]].sum()
    schritte = [("Miete", s["Miete"], "total0"), ("Fixkosten", -s["Fixkosten"], "rel"), ("Instandhaltung", -s["Instandhaltung"], "rel"),
                ("Zins", -s["Zins"], "rel"), ("Tilgung", -s["Tilgung"], "rel"), ("Massnahmen", -s["Massnahmen"], "rel"),
                ("Ausschuettung", -s["Ausschuettung"], "rel"), ("Nachschuss", s["Nachschuss"], "rel")]
    schritte = [x for x in schritte if abs(x[1]) > 0.5]
    x = [LABEL[k] for k, _, _ in schritte] + ["Veränderung Kontostand"]
    y = [v for _, v, _ in schritte] + [0]
    meas = ["absolute" if m == "total0" else "relative" for _, _, m in schritte] + ["total"]
    fig = go.Figure(go.Waterfall(x=x, y=y, measure=meas, connector=dict(line=dict(color=BASE, width=1)),
                                 increasing=dict(marker=dict(color=C["Miete"])), decreasing=dict(marker=dict(color="#898781")),
                                 totals=dict(marker=dict(color="#184f95")), texttemplate="%{y:,.0f}", textposition="outside",
                                 textfont=dict(size=12, color=TINTE), hovertemplate="%{x}: %{y:,.0f} €<extra></extra>"))
    fig.update_yaxes(title_text=f"€ ({titel})", tickformat=",.0f")
    fig.update_xaxes(tickangle=-20)
    fig.update_layout(margin=dict(b=110))
    return _layout(fig, 440, legende=False)


def fig_kapitaldienst(a: Analyse) -> go.Figure:
    g = a.basis.monat
    p = a.daten.params
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4], vertical_spacing=0.08)
    for k in ["Zins", "Tilgung"]:
        fig.add_trace(go.Bar(x=g.index, y=g[k], name=LABEL[k], marker_color=C[k], marker_line=dict(color="#fcfcfb", width=2),
                             hovertemplate="%{x|%m/%Y}: %{y:,.0f} €<extra>" + LABEL[k] + "</extra>"), row=1, col=1)
    dscr = g["NOI"] / g["Kapitaldienst"]
    fig.add_trace(go.Scatter(x=g.index, y=dscr, name="DSCR", mode="lines+markers", line=dict(color=C["Miete"], width=2.5),
                             marker=dict(size=8, line=dict(color="#fcfcfb", width=2)), hovertemplate="%{x|%m/%Y}: %{y:.2f}<extra>DSCR</extra>"), row=2, col=1)
    fig.add_hline(y=p["dscr_gruen"], line=dict(color=STATUS[GRUEN], dash="dot", width=1.5), row=2, col=1,
                  annotation_text=f"grün ≥ {dz(p['dscr_gruen'])}", annotation_position="top left", annotation_font=dict(size=11, color=TINTE2))
    fig.add_hline(y=p["dscr_gelb"], line=dict(color=STATUS[ROT], dash="dot", width=1.5), row=2, col=1,
                  annotation_text=f"kritisch < {dz(p['dscr_gelb'])}", annotation_position="bottom left", annotation_font=dict(size=11, color=TINTE2))
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title_text="€ pro Monat", tickformat=",.0f", row=1, col=1)
    fig.update_yaxes(title_text="DSCR", rangemode="tozero", row=2, col=1)
    fig.update_xaxes(tickformat="%m/%Y", dtick="M1")
    return _layout(fig, 560)


def fig_massnahmen(a: Analyse) -> go.Figure:
    d = a.daten
    mk = a.ergebnisse["Basis"].massnahmen
    fig = go.Figure()
    if mk.empty:
        return _layout(fig, 300, legende=False)
    mk = mk[(mk["Status"] != "entfallen") & mk["Monat"].isin(d.monate)].copy()
    ist = mk["Monat"] <= d.letzter_ist
    mk["Betrag"] = np.where(ist, mk["Kosten_ist"].fillna(0), mk["Kosten_erwartet"])
    mk["Plus"] = np.where(ist, 0, mk["Kosten_max"] - mk["Kosten_erwartet"])
    mk["Minus"] = np.where(ist, 0, mk["Kosten_erwartet"] - mk["Kosten_min"])
    # nach Maßnahme gestapelt, Reihenfolge nach Termin
    for _, r in mk.sort_values(["Monat", "Massnahme_ID"]).iterrows():
        fig.add_trace(go.Bar(
            x=[r["Monat"]], y=[r["Betrag"]], name=f"{r['Massnahme_ID']} {r['Bezeichnung']} ({r['Objekt_ID']})",
            marker=dict(color=C["Massnahmen"] if r["Monat"] > d.letzter_ist else "#898781", line=dict(color="#fcfcfb", width=2),
                        pattern_shape="" if r["Status"] in ("beauftragt", "abgeschlossen") else "/"),
            error_y=dict(type="data", symmetric=False, array=[r["Plus"]], arrayminus=[r["Minus"]], color=TINTE2, thickness=1.2, width=4),
            hovertemplate=(f"<b>{r['Bezeichnung']}</b> ({r['Objekt_ID']})<br>Status: {r['Status']}<br>erwartet: {eur(r['Betrag'])}"
                           f"<br>Spanne: {eur(r['Betrag'] - r['Minus'])} – {eur(r['Betrag'] + r['Plus'])}<extra></extra>")))
    fig.update_layout(barmode="stack")
    _grenze(fig, a)
    fig.update_yaxes(title_text="Kosten je Monat", tickformat=",.0f", ticksuffix=" €")
    fig.update_xaxes(tickformat="%m/%Y", dtick="M1")
    _layout(fig, 520)
    fig.update_layout(legend=dict(orientation="h", y=-0.14, x=0), margin=dict(b=140))
    return fig


def fig_deckung(a: Analyse) -> go.Figure:
    k = a.kpis
    offen_max = float(a.ergebnisse["Pessimistisch"].massnahmen.query("Monat > @a.daten.letzter_ist")["Kosten_szenario"].sum()) if len(a.basis.massnahmen) else 0.0
    zeilen = [("Offene Maßnahmen (erwartet)", k["massn_offen"].wert, C["Massnahmen"]),
              ("Offene Maßnahmen (Maximum)", offen_max, "#d55181"),
              ("Kontostand heute", k["kontostand"].wert, C["Miete"]),
              ("Rückstellungen (bilanziell)", k["rueckstellung"].wert, "#898781")]
    fig = go.Figure(go.Bar(y=[z[0] for z in zeilen], x=[z[1] for z in zeilen], orientation="h", marker_color=[z[2] for z in zeilen],
                           marker_line=dict(color="#fcfcfb", width=2), text=[eur(z[1]) for z in zeilen], textposition="outside",
                           textfont=dict(color=TINTE), hovertemplate="%{y}: %{x:,.0f} €<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickformat=",.0f", ticksuffix=" €", range=[0, max(z[1] for z in zeilen) * 1.2])
    fig.update_layout(margin=dict(l=210))
    return _layout(fig, 300, legende=False)


def fig_heatmap(a: Analyse) -> go.Figure:
    om = a.basis.objekt_monat
    ok = a.objekt_kpis.set_index("Objekt_ID")
    piv = om.pivot(index="Objekt_ID", columns="Monat", values="CF_objekt").reindex(ok.sort_values("DSCR").index)
    labels = [f"{i} · {ok.loc[i, 'Name'][:34]}" for i in piv.index]
    zmax = float(np.nanmax(np.abs(piv.values))) or 1
    fig = go.Figure(go.Heatmap(z=piv.values, x=[_mon(m) for m in piv.columns], y=labels, zmid=0, zmin=-zmax, zmax=zmax,
                               colorscale=[[0, "#c03a39"], [0.25, "#e8928f"], [0.5, "#f0efec"], [0.75, "#86b6ef"], [1, "#184f95"]],
                               xgap=2, ygap=2, colorbar=dict(title="€", thickness=12, tickformat=",.0f"),
                               hovertemplate="%{y}<br>%{x}: %{z:,.0f} €<extra></extra>"))
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=11))
    fig.update_layout(margin=dict(l=260))
    return _layout(fig, max(420, 22 * len(labels) + 90), legende=False)


def fig_dscr_objekte(a: Analyse) -> go.Figure:
    ok = a.objekt_kpis.sort_values("DSCR", ascending=True)
    p = a.daten.params
    farben = [STATUS.get(x, "#898781") for x in ok["Ampel_DSCR"]]
    fig = go.Figure(go.Bar(y=[f"{n[:36]}" for n in ok["Name"]], x=ok["DSCR"], orientation="h", marker_color=farben,
                           marker_line=dict(color="#fcfcfb", width=1.5),
                           text=[f"{'■' if r == ROT else '▲' if r == GELB else '●'} {dz(v)}" for v, r in zip(ok["DSCR"], ok["Ampel_DSCR"])],
                           textposition="outside", textfont=dict(size=11, color=TINTE),
                           hovertemplate="%{y}<br>DSCR %{x:.2f}<extra></extra>"))
    fig.add_vline(x=p["dscr_gruen"], line=dict(color=STATUS[GRUEN], dash="dot", width=1.5))
    fig.add_vline(x=p["dscr_gelb"], line=dict(color=STATUS[ROT], dash="dot", width=1.5))
    fig.update_xaxes(title_text="DSCR (NOI ÷ Kapitaldienst), Ist-Zeitraum", range=[0, max(2.0, float(ok["DSCR"].max()) * 1.15)])
    fig.update_yaxes(tickfont=dict(size=11))
    fig.update_layout(margin=dict(l=260))
    return _layout(fig, max(420, 20 * len(ok) + 90), legende=False)


def fig_auslastung_be(a: Analyse) -> go.Figure:
    ok = a.objekt_kpis
    mx = float(max(ok["Break_even_Auslastung"].max(), 1.0))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0.4, 1.05], y=[0.4, 1.05], mode="lines", line=dict(color=BASE, dash="dot"), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(
        x=ok["Break_even_Auslastung"], y=ok["Auslastung"], mode="markers",
        marker=dict(size=np.clip(ok["Miete"] / ok["Miete"].max() * 28, 8, 28), color=[STATUS.get(x, "#898781") for x in ok["Ampel_DSCR"]],
                    symbol=["square" if r == ROT else "triangle-up" if r == GELB else "circle" for r in ok["Ampel_DSCR"]],
                    line=dict(color="#fcfcfb", width=2), opacity=0.9),
        text=ok["Name"], customdata=ok["DSCR"], showlegend=False,
        hovertemplate="%{text}<br>Auslastung %{y:.1%}<br>Break-even %{x:.1%}<br>DSCR %{customdata:.2f}<extra></extra>"))
    fig.add_annotation(x=0.99, y=0.44, text="unterhalb der Linie: Kosten nicht gedeckt", showarrow=False, xanchor="right", font=dict(size=12, color=TINTE2))
    fig.update_xaxes(title_text="Break-even-Auslastung (alle Kosten inkl. Kapitaldienst gedeckt)", tickformat=".0%", range=[0.4, min(mx * 1.05, 1.3)])
    fig.update_yaxes(title_text="Tatsächliche Auslastung", tickformat=".0%", range=[0.4, 1.05])
    return _layout(fig, 460, legende=False)


def fig_nutzung(a: Analyse) -> go.Figure:
    nk = a.nutzung_kpis.sort_values("Miete", ascending=False)
    p = a.daten.params
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Anteil an der Miete", "DSCR"), horizontal_spacing=0.14)
    fig.add_trace(go.Bar(y=nk["Nutzung"], x=nk["Miete"] / nk["Miete"].sum(), orientation="h", marker_color=C["Miete"], marker_line=dict(color="#fcfcfb", width=2),
                         text=[f"{v:.0%}" for v in nk["Miete"] / nk["Miete"].sum()], textposition="outside", showlegend=False,
                         hovertemplate="%{y}: %{x:.1%}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(y=nk["Nutzung"], x=nk["DSCR"], orientation="h", marker_color=[STATUS.get(r, "#898781") for r in
                         [("gruen" if v >= p["dscr_gruen"] else "gelb" if v >= p["dscr_gelb"] else "rot") for v in nk["DSCR"]]],
                         marker_line=dict(color="#fcfcfb", width=2), text=[dz(v) for v in nk["DSCR"]], textposition="outside", showlegend=False,
                         hovertemplate="%{y}: DSCR %{x:.2f}<extra></extra>"), row=1, col=2)
    fig.update_xaxes(tickformat=".0%", range=[0, 1], row=1, col=1)
    fig.update_xaxes(range=[0, max(2.0, float(nk["DSCR"].max()) * 1.2)], row=1, col=2)
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, 300, legende=False)


def fig_tornado(a: Analyse) -> go.Figure:
    t = a.sensitivitaet.iloc[::-1]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=t["Faktor"], x=t["Delta_schlecht"], orientation="h", name="Ungünstig", marker_color="#eb6834",
                         marker_line=dict(color="#fcfcfb", width=2), customdata=t["Schlecht_Label"],
                         hovertemplate="%{customdata}<br>Δ tiefster Kontostand: %{x:,.0f} €<extra></extra>"))
    fig.add_trace(go.Bar(y=t["Faktor"], x=t["Delta_gut"], orientation="h", name="Günstig", marker_color="#2a78d6",
                         marker_line=dict(color="#fcfcfb", width=2), customdata=t["Gut_Label"],
                         hovertemplate="%{customdata}<br>Δ tiefster Kontostand: %{x:,.0f} €<extra></extra>"))
    fig.update_layout(barmode="relative")
    fig.update_xaxes(title_text="Veränderung des tiefsten Kontostands ggü. Basis (€)", tickformat=",.0f")
    return _layout(fig, 380)


def fig_zinsbindung(a: Analyse) -> go.Figure:
    o = a.objekt_kpis.dropna(subset=["Zinsbindung_bis", "Restschuld"]).copy()
    o["Jahr"] = o["Zinsbindung_bis"].dt.year
    ende = a.daten.letzter_ist
    g = o.groupby("Jahr").agg(Restschuld=("Restschuld", "sum"), Anzahl=("Objekt_ID", "count"), Zins=("Zinssatz", "mean")).reset_index()
    fig = go.Figure(go.Bar(x=g["Jahr"].astype(str), y=g["Restschuld"], marker_color=C["Zins"], marker_line=dict(color="#fcfcfb", width=2),
                           customdata=np.stack([g["Anzahl"], g["Zins"]], axis=-1),
                           text=[f"{n} Darl." for n in g["Anzahl"]], textposition="outside", textfont=dict(color=TINTE),
                           hovertemplate="Ablauf %{x}<br>Restschuld %{y:,.0f} €<br>%{customdata[0]} Darlehen, Ø Zins %{customdata[1]:.2%}<extra></extra>"))
    fig.update_yaxes(title_text="Restschuld bei Zinsbindungsende", tickformat=",.0f", ticksuffix=" €")
    fig.update_xaxes(type="category", title_text="Jahr des Zinsbindungsendes")
    return _layout(fig, 360, legende=False)


def alle(a: Analyse) -> dict[str, go.Figure]:
    d = a.daten
    return {
        "kontostand": fig_kontostand(a),
        "cashflow": fig_cashflow(a),
        "wasserfall_ist": fig_wasserfall(a, d.ist_monate, f"Ist {_mon(d.ist_monate[0])}–{_mon(d.ist_monate[-1])}"),
        "wasserfall_plan": fig_wasserfall(a, d.plan_monate, f"Prognose {_mon(d.plan_monate[0])}–{_mon(d.plan_monate[-1])}") if d.plan_monate else go.Figure(),
        "kapitaldienst": fig_kapitaldienst(a),
        "massnahmen": fig_massnahmen(a),
        "deckung": fig_deckung(a),
        "heatmap": fig_heatmap(a),
        "dscr_objekte": fig_dscr_objekte(a),
        "auslastung_be": fig_auslastung_be(a),
        "nutzung": fig_nutzung(a),
        "tornado": fig_tornado(a),
        "zinsbindung": fig_zinsbindung(a),
    }
