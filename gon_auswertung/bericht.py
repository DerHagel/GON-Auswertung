"""HTML-Bericht (selbstenthalten, druckbar), optional PDF über headless Chromium."""
from __future__ import annotations

import html
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment

from . import grafiken
from .kennzahlen import GELB, GRUEN, ROT, SYMBOL, TEXT, Analyse, Kpi
from .modell import min_kontostand
from .profile import ABSCHNITT_TITEL, ABSCHNITTE, Profil, lade_profil


def _fmt(k: Kpi) -> str:
    v = k.wert
    if v is None or pd.isna(v):
        return "–"
    if k.einheit == "eur":
        return f"{v:,.0f} €".replace(",", ".")
    if k.einheit == "x":
        return f"{v:.2f}".replace(".", ",")
    if k.einheit == "pct":
        return f"{v * 100:.1f} %".replace(".", ",")
    if k.einheit == "mon":
        return f"{v:.1f}".replace(".", ",") + " Mon."
    return str(v)


def _eur(x) -> str:
    return "–" if pd.isna(x) else f"{x:,.0f}".replace(",", ".")


def _tabelle(df: pd.DataFrame, formate: dict[str, str], ampel_spalten: dict[str, str] | None = None, verstecke: list[str] | None = None) -> str:
    ampel_spalten = ampel_spalten or {}
    verstecke = verstecke or []
    spalten = [c for c in df.columns if c not in verstecke]
    kopf = "".join(f"<th>{html.escape(c)}</th>" for c in spalten)
    zeilen = []
    for _, r in df.iterrows():
        zellen = []
        for c in spalten:
            v = r[c]
            f = formate.get(c)
            if f == "eur":
                txt = _eur(v)
            elif f == "pct":
                txt = "–" if pd.isna(v) else f"{v * 100:.1f} %".replace(".", ",")
            elif f == "x2":
                txt = "–" if pd.isna(v) else f"{v:.2f}".replace(".", ",")
            elif f == "datum":
                txt = "–" if pd.isna(v) else f"{v:%m/%Y}"
            elif f == "int":
                txt = "–" if pd.isna(v) else f"{v:,.0f}".replace(",", ".")
            else:
                txt = html.escape(str(v))
            cls = "num" if f else ""
            if c in ampel_spalten and r.get(ampel_spalten[c]) in SYMBOL:
                a = r[ampel_spalten[c]]
                txt = f'<span class="amp {a}" title="{TEXT[a]}">{SYMBOL[a]}</span> {txt}'
            zellen.append(f'<td class="{cls}">{txt}</td>')
        zeilen.append("<tr>" + "".join(zellen) + "</tr>")
    return f'<div class="tw"><table><thead><tr>{kopf}</tr></thead><tbody>{"".join(zeilen)}</tbody></table></div>'


CSS = """
:root{--bg:#f9f9f7;--card:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--line:#e1e0d9;--accent:#184f95;--gruen:#0ca30c;--gelb:#fab219;--rot:#d03b3b}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0d0d0d;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--line:#2c2c2a;--accent:#86b6ef}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:28px 24px 8px;max-width:1280px;margin:auto}h1{margin:0;font-size:26px}h2{font-size:21px;margin:0 0 4px}h3{font-size:16px;margin:22px 0 4px}
.sub{color:var(--ink2);margin:4px 0 0}main{max-width:1280px;margin:auto;padding:0 24px 60px}
nav{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);z-index:5;padding:8px 24px}
nav div{max-width:1280px;margin:auto;display:flex;flex-wrap:wrap;gap:6px 18px;font-size:14px}nav a{color:var(--accent);text-decoration:none}nav a:hover{text-decoration:underline}
section{margin-top:34px}.lead{color:var(--ink2);margin:0 0 12px;max-width:900px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:14px 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;border-top:4px solid var(--line)}
.tile.gruen{border-top-color:var(--gruen)}.tile.gelb{border-top-color:var(--gelb)}.tile.rot{border-top-color:var(--rot)}
.tile .t{font-size:13px;color:var(--ink2)}.tile .v{font-size:26px;font-weight:650;margin:2px 0}.tile .s{font-size:12.5px;color:var(--ink2)}
.amp{font-weight:700}.amp.gruen{color:var(--gruen)}.amp.gelb{color:#c98500}.amp.rot{color:var(--rot)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}
.grid2>*{min-width:0}.plot{min-width:0}.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:12px}
.kom li{margin:6px 0}.hint{font-size:13px;color:var(--ink2)}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{padding:6px 9px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{position:sticky;top:0;background:var(--card);color:var(--ink2);font-weight:600}td.num{text-align:right;font-variant-numeric:tabular-nums}
.warn{border-left:4px solid var(--gelb);padding:6px 12px;margin:6px 0;background:var(--card)}.info{border-left:4px solid var(--muted);padding:6px 12px;margin:6px 0;background:var(--card)}
details{margin:8px 0}summary{cursor:pointer;color:var(--accent)}
.chart{margin:0}.plot{border-radius:8px;overflow:hidden}
@media print{nav{display:none}body{background:#fff}section{page-break-inside:avoid;margin-top:20px}.card,.tile{break-inside:avoid}.tw{overflow:visible}}
@media (max-width:560px){.grid2{grid-template-columns:1fr}header,main,nav{padding-left:14px;padding-right:14px}}
"""

SECTIONS = {
    'zusammenfassung': '<section id="zusammenfassung"><h2>Zusammenfassung</h2>\n<p class="lead">Die wichtigsten Kennzahlen auf einen Blick. Symbole und Farben: ● in Ordnung · ▲ beobachten · ■ kritisch (Schwellen im Parameter-Blatt einstellbar).</p>\n<div class="tiles">{% for k in tiles %}<div class="tile {{ k.status or \'\' }}"><div class="t">{{ k.titel }}</div><div class="v">{% if k.status %}<span class="amp {{ k.status }}">{{ sym[k.status] }}</span> {% endif %}{{ k.text }}</div><div class="s">{{ k.formel }}</div></div>{% endfor %}</div>\n{% if kommentar %}<div class="card"><h3 style="margin-top:0">Kernaussagen</h3><ul class="kom">{% for s in kommentar %}<li>{{ s }}</li>{% endfor %}</ul></div>{% endif %}\n{{ fig(\'kontostand\', \'Kontostand: Ist und Prognose mit Szenario-Korridor\', \'Die Kurve zeigt die kumulierte Liquidität. Das blaue Band reicht vom optimistischen bis zum pessimistischen Szenario; die gepunktete rote Linie ist die Mindestliquidität.\') }}\n</section>',
    'liquiditaet': '<section id="liquiditaet"><h2>Liquidität</h2>\n<p class="lead">Woher kommt das Geld, wohin fließt es – und wann wird es eng?</p>\n{{ fig(\'cashflow\', \'Mieteinnahmen gegenüber Kosten je Monat\', \'Liegt die Mietlinie über den gestapelten Kosten, entsteht ein Überschuss. Außerordentliche Maßnahmen (rosa) erzeugen die Spitzen.\') }}\n<div class="grid2">{{ fig(\'wasserfall_ist\', \'Wohin die Miete fließt – Ist-Zeitraum\', \'Von der Miete bleibt nach allen Kosten und Ausschüttungen die Veränderung des Kontostands.\') }}\n{{ fig(\'wasserfall_plan\', \'Wohin die Miete fließt – Prognosezeitraum\', \'Gleiche Darstellung für die Plan-Monate (Basisszenario).\') }}</div>\n{% if t_monat %}<h3>Monatsübersicht Basisszenario</h3>{{ t_monat }}{% endif %}\n</section>',
    'finanzierung': '<section id="finanzierung"><h2>Finanzierung (Sicht der Banken)</h2>\n<p class="lead">Trägt das Betriebsergebnis den Kapitaldienst, wie robust ist die Auslastung und wann laufen Zinsbindungen aus?</p>\n<div class="tiles">{% for k in fin_tiles %}<div class="tile {{ k.status or \'\' }}"><div class="t">{{ k.titel }}</div><div class="v">{% if k.status %}<span class="amp {{ k.status }}">{{ sym[k.status] }}</span> {% endif %}{{ k.text }}</div><div class="s">{{ k.erklaerung }}</div></div>{% endfor %}</div>\n{{ fig(\'kapitaldienst\', \'Kapitaldienst und Kapitaldienstdeckung (DSCR)\', \'Oben: Zins und Tilgung. Unten: Wie oft das Betriebsergebnis den Kapitaldienst deckt; unter der roten Linie reicht es nicht.\') }}\n<div class="grid2">{{ fig(\'auslastung_be\', \'Auslastung gegenüber Break-even je Objekt\', \'Objekte oberhalb der Diagonalen decken ihre Kosten inkl. Kapitaldienst; die Punktgröße zeigt die Miethöhe.\') }}\n{{ fig(\'zinsbindung\', \'Anschlussfinanzierung: Restschuld nach Zinsbindungsende\', \'Je höher der Balken, desto mehr Refinanzierungs- und Zinsänderungsrisiko in diesem Jahr.\') }}</div>\n</section>',
    'instandhaltung': '<section id="instandhaltung"><h2>Instandhaltung & Maßnahmen</h2>\n<p class="lead">Außerordentliche Maßnahmen mit Kostenspanne (Fehlerbalken = Minimum bis Maximum). Schraffiert = geplant, ausgefüllt = beauftragt/abgeschlossen.</p>\n{{ fig(\'massnahmen\', \'Maßnahmen nach Monat\', \'Grau = bereits angefallen (Ist), rosa = Prognose. Die Spannweite zeigt die Kostenunsicherheit.\') }}\n{{ fig(\'deckung\', \'Sind die offenen Maßnahmen gedeckt?\', \'Rückstellungen sind aktuell nur bilanziell. Entscheidend ist, ob der Kontostand die Maßnahmen tragen kann.\') }}\n{% if t_massn %}<h3>Maßnahmenliste</h3>{{ t_massn }}{% endif %}\n</section>',
    'portfolio': '<section id="portfolio"><h2>Portfolio</h2>\n<p class="lead">Wo liegen Stärken und Schwächen im Bestand? Objekte sind nach DSCR sortiert (schwächste zuerst bzw. oben).</p>\n{{ fig(\'nutzung\', \'Nutzungsarten im Vergleich\', \'Mietanteil und Kapitaldienstdeckung je Nutzungsart.\') }}\n{{ fig(\'dscr_objekte\', \'DSCR je Objekt\', \'Jedes Objekt gegen die Schwellen: grün ≥ Zielwert, gelb dazwischen, rot kritisch.\') }}\n{{ fig(\'heatmap\', \'Cashflow je Objekt und Monat (nach Maßnahmen)\', \'Blau = Überschuss, rot = Defizit, grau = ausgeglichen. Schwächste Objekte stehen oben.\') }}\n{% if t_obj %}<h3>Objektkennzahlen (Ist-Zeitraum)</h3>{{ t_obj }}{% endif %}\n{% if t_nutz %}<h3>Nutzungsarten</h3>{{ t_nutz }}{% endif %}\n</section>',
    'szenarien': '<section id="szenarien"><h2>Szenarien & Risiko</h2>\n<p class="lead">Was passiert, wenn es anders kommt? Basis = erwartete Kosten · Optimistisch = Minimalkosten · Pessimistisch = Maximalkosten, zusätzlicher Mietausfall und Zinsaufschlag bei auslaufender Bindung.</p>\n{% if t_szen %}{{ t_szen }}{% endif %}\n<div class="tiles">\n<div class="tile"><div class="t">Nachschussbedarf im Stressfall</div><div class="v">{{ eur(stress.nachschuss) }}</div><div class="s">Betrag, der fehlt, um die Mindestliquidität zu halten</div></div>\n<div class="tile"><div class="t">Ausschüttungsspielraum (Stressfall)</div><div class="v">{{ eur(stress.ausschuettung_max) }}</div><div class="s">Ausschüttung, die zusätzlich möglich wäre, ohne die Mindestliquidität im Stressfall zu verletzen</div></div>\n<div class="tile"><div class="t">Verkraftbarer Mietausfall</div><div class="v">{{ \'%.1f\'|format(stress.leerstand_be*100)|replace(\'.\',\',\') }} %</div><div class="s">zusätzlicher Mietausfall bis die Mindestliquidität erreicht ist (Basis-Maßnahmen)</div></div></div>\n{{ fig(\'tornado\', \'Sensitivität: Was beeinflusst den tiefsten Kontostand am stärksten?\', \'Längere Balken = größerer Einfluss. Zinsen wirken nur auf Darlehen, deren Zinsbindung im Prognosezeitraum endet.\') }}\n</section>',
    'methodik': '<section id="methodik"><h2>Daten & Methodik</h2>\n<h3>Hinweise zur Datenqualität</h3>\n{% for stufe, text in meldungen %}<div class="{{ \'warn\' if stufe==\'warn\' else \'info\' }}">{{ text }}</div>{% else %}<div class="info">Keine Auffälligkeiten.</div>{% endfor %}\n{% if t_abst %}<h3>Kontoabstimmung (Ist-Monate)</h3>{{ t_abst }}{% endif %}\n{% if t_gloss %}<h3>Kennzahlen-Glossar</h3>{{ t_gloss }}{% endif %}\n<details><summary>Rechenlogik</summary><div class="card"><ul>\n<li><b>NOI</b> = Miete − feste Kosten − laufende Instandhaltung (ohne Kapitaldienst).</li>\n<li><b>Cashflow vor Maßnahmen</b> = NOI − Zins − Tilgung. <b>Netto-Cashflow</b> = Cashflow vor Maßnahmen − außerordentliche Instandhaltung − Ausschüttung + Nachschuss.</li>\n<li><b>Kontostand</b>: Ist-Monate laut Konto; Prognose = letzter Ist-Kontostand + Netto-Cashflow.</li>\n<li><b>Rückstellungen</b> sind rein bilanziell und beeinflussen die Liquidität nicht; sie werden nur den Maßnahmen gegenübergestellt.</li>\n<li><b>Szenarien</b> verändern ausschließlich Plan-Monate. Ist-Monate bleiben unverändert.</li></ul></div></details>\n</section>',
    'gesellschafter': '<section id="gesellschafter"><h2>Gesellschafter</h2>\n<p class="lead">Anteile nach Beteiligungsquote. Reine Quotenbetrachtung ohne steuerliche Wirkung; maßgeblich sind Gesellschaftsvertrag und Beschlüsse.</p>\n{% if person_tiles %}<h3 style="margin-top:0">{{ person }}</h3><div class="tiles">{% for t in person_tiles %}<div class="tile"><div class="t">{{ t.titel }}</div><div class="v">{{ t.text }}</div><div class="s">{{ t.erkl }}</div></div>{% endfor %}</div>{% endif %}\n{% if t_ges %}<h3>Übersicht nach Gesellschaftern</h3>{{ t_ges }}{% endif %}\n{% if not person_tiles and not t_ges %}<div class="info">Keine Gesellschafterdaten erfasst (Blatt „Gesellschafter“).</div>{% endif %}\n</section>',
}
HEAD = """<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ titel }}</title><style>{{ css }}</style></head><body>
<header><h1>{{ titel }}</h1>
<p class="sub">Stand: letzter Ist-Monat {{ stand }} · Prognose bis {{ ende }} · {{ n_obj }} Objekte · erstellt {{ erstellt }}{% if person %} · für {{ person }}{% endif %}</p>
{% if zielgruppe %}<p class="sub">{{ zielgruppe }}</p>{% endif %}{% if einleitung %}<p class="lead" style="margin-top:10px">{{ einleitung }}</p>{% endif %}</header>
<nav><div>{% for k, t in nav %}<a href="#{{ k }}">{{ t }}</a>{% endfor %}</div></nav>
<main>
"""
FOOT = """</main>
<script>
function gonResize(){document.querySelectorAll('.js-plotly-plot').forEach(function(p){try{Plotly.Plots.resize(p)}catch(e){}})}
window.addEventListener('load',function(){gonResize();setTimeout(gonResize,300)});window.addEventListener('beforeprint',gonResize);
</script></body></html>"""



LIQUIDITAETSKACHELN = {"kontostand", "min_basis", "min_pess", "puffer", "kassen_deckung", "cf_ist"}


def baue_html(a: Analyse, profil: Profil | None = None, person: str | None = None) -> str:
    profil = profil or lade_profil("geschaeftsfuehrung")
    d = a.daten
    aus = set(profil.ausblenden)
    abschnitte = [x for x in profil.abschnitte if x in ABSCHNITTE]       # Reihenfolge wie im Profil
    themen = set(profil.kommentar_themen)
    kacheln, fin_kacheln = list(profil.kacheln), list(profil.fin_kacheln)
    if profil.gefiltert:      # Teilportfolio: Liquidität/Konto gehört zur Gesamtgesellschaft
        abschnitte = [x for x in abschnitte if x not in ("liquiditaet", "szenarien", "gesellschafter")]
        themen.discard("liquiditaet")
        kacheln = [x for x in kacheln if x not in LIQUIDITAETSKACHELN]
        aus |= {"kontostand", "cashflow", "wasserfall_ist", "wasserfall_plan", "tornado", "t_monat", "t_abst", "t_szen"}
    figs = {k: v for k, v in grafiken.alle(a).items() if k not in aus}
    erste = [True]

    def fig(key: str, titel: str, erkl: str) -> str:
        if key not in figs:
            return ""
        f = figs[key]
        js = "inline" if erste[0] else False
        erste[0] = False
        div = f.to_html(full_html=False, include_plotlyjs=js, config={"displaylogo": False, "responsive": True, "displayModeBar": False})
        return f'<div class="card chart"><h3 style="margin-top:0">{html.escape(titel)}</h3><p class="hint">{html.escape(erkl)}</p><div class="plot">{div}</div></div>'

    k = a.kpis
    tiles = [k[x] for x in kacheln]
    fin = [k[x] for x in fin_kacheln]
    mk = lambda lst: [{"titel": x.titel, "text": _fmt(x), "status": x.status, "formel": x.formel, "erklaerung": x.erklaerung} for x in lst]

    g = a.basis.monat.copy()
    g.insert(0, "Zeitraum", [f"{m:%m/%Y}" for m in g.index])
    g["Phase"] = g["Typ"]
    t_monat = _tabelle(g[["Zeitraum", "Phase", "Miete", "Fixkosten", "Zins", "Tilgung", "Instandhaltung", "Massnahmen", "Ausschuettung", "NOI", "CF_netto", "Kontostand"]].rename(columns={"Massnahmen": "Außerord. IH", "CF_netto": "Netto-CF", "Ausschuettung": "Ausschüttung"}),
                       {c: "eur" for c in ["Miete", "Fixkosten", "Zins", "Tilgung", "Instandhaltung", "Außerord. IH", "Ausschüttung", "NOI", "Netto-CF", "Kontostand"]})

    m = a.basis.massnahmen
    if len(m):
        mm = m.sort_values("Monat")[["Massnahme_ID", "Objekt_ID", "Bezeichnung", "Monat", "Status", "Kosten_min", "Kosten_erwartet", "Kosten_max", "Kosten_ist"]].rename(columns={"Massnahme_ID": "ID", "Objekt_ID": "Objekt", "Kosten_min": "Min", "Kosten_erwartet": "Erwartet", "Kosten_max": "Max", "Kosten_ist": "Ist"})
        t_massn = _tabelle(mm, {"Monat": "datum", "Min": "eur", "Erwartet": "eur", "Max": "eur", "Ist": "eur"})
    else:
        t_massn = '<div class="info">Keine Maßnahmen erfasst.</div>'

    ok = a.objekt_kpis.sort_values("DSCR")
    ot = ok[["Objekt_ID", "Name", "Nutzung", "Miete", "Auslastung", "NOI_Marge", "DSCR", "LTV", "NOI_Rendite_pa", "IH_je_qm_pa", "Zinsbindung_bis", "Risiko_Score", "Ampel_DSCR"]].rename(
        columns={"Objekt_ID": "ID", "NOI_Marge": "NOI-Marge", "NOI_Rendite_pa": "NOI-Rendite p. a.", "IH_je_qm_pa": "Instandh. €/m² p. a.", "Zinsbindung_bis": "Zinsbindung bis", "Risiko_Score": "Risiko"})
    t_obj = _tabelle(ot, {"Miete": "eur", "Auslastung": "pct", "NOI-Marge": "pct", "DSCR": "x2", "LTV": "pct", "NOI-Rendite p. a.": "pct",
                          "Instandh. €/m² p. a.": "x2", "Zinsbindung bis": "datum", "Risiko": "int"}, {"DSCR": "Ampel_DSCR"}, verstecke=["Ampel_DSCR"])

    nk = a.nutzung_kpis[["Nutzung", "Objekte", "Flaeche_qm", "Verkehrswert", "Restschuld", "Miete", "Auslastung", "NOI", "NOI_Marge", "DSCR", "LTV"]].rename(columns={"Flaeche_qm": "Fläche m²", "NOI_Marge": "NOI-Marge"})
    t_nutz = _tabelle(nk, {"Objekte": "int", "Fläche m²": "int", "Verkehrswert": "eur", "Restschuld": "eur", "Miete": "eur", "Auslastung": "pct", "NOI": "eur", "NOI-Marge": "pct", "DSCR": "x2", "LTV": "pct"})

    zeilen = []
    for name, e in a.ergebnisse.items():
        mn, wann = min_kontostand(e)
        z = e.monat
        zeilen.append({"Szenario": name, "Tiefster Kontostand": mn, "im Monat": wann, "Endstand": z["Kontostand"].iloc[-1],
                       "Maßnahmen Prognose": z.loc[z["Typ"] == "Plan", "Massnahmen"].sum(), "Netto-CF Prognose": z.loc[z["Typ"] == "Plan", "CF_netto"].sum(),
                       "Unterdeckung Mindestliq.": max(0.0, d.params["mindestliquiditaet"] - mn)})
    t_szen = _tabelle(pd.DataFrame(zeilen), {c: "eur" for c in ["Tiefster Kontostand", "Endstand", "Maßnahmen Prognose", "Netto-CF Prognose", "Unterdeckung Mindestliq."]} | {"im Monat": "datum"})

    t_ges, person_tiles = "", []
    if len(a.gesellschafter):
        gs = a.gesellschafter
        if person:
            zeile = gs[gs["Name"] == person]
            if zeile.empty:
                raise ValueError(f"Gesellschafter '{person}' nicht gefunden. Vorhanden: {', '.join(gs['Name'])}")
            r = zeile.iloc[0]
            person_tiles = [
                {"titel": "Beteiligungsquote", "text": f"{r['Quote'] * 100:.1f} %".replace(".", ","), "erkl": "Anteil am Gesellschaftskapital laut Blatt Gesellschafter"},
                {"titel": "Anteil am Kontostand", "text": _eur(r["Anteil_Kontostand"]) + " €", "erkl": "Quote × Kontostand (letzter Ist-Monat)"},
                {"titel": "Ausschüttungen im Ist-Zeitraum", "text": _eur(r["Ausschuettung_Ist"]) + " €", "erkl": "Quote × ausgeschüttete Beträge"},
                {"titel": "Geplante Ausschüttungen", "text": _eur(r["Ausschuettung_Plan"]) + " €", "erkl": "Quote × geplante Ausschüttungen im Prognosezeitraum"},
                {"titel": "Anteil an offenen Maßnahmen", "text": _eur(r["Anteil_Massnahmen_offen"]) + " €", "erkl": "Quote × erwartete Kosten offener Maßnahmen"},
                {"titel": "Nachschuss im Stressfall", "text": _eur(r["Nachschuss_Stress"]) + " €", "erkl": "Quote × Fehlbetrag zur Mindestliquidität im pessimistischen Szenario"},
                {"titel": "Ausschüttungsspielraum", "text": _eur(r["Ausschuettung_Spielraum"]) + " €", "erkl": "Quote × zusätzlich mögliche Ausschüttung, ohne im Stressfall die Mindestliquidität zu verletzen"},
                {"titel": "Anteil am Nettovermögen", "text": _eur(r["Anteil_Nettovermoegen"]) + " €", "erkl": "Quote × (Verkehrswert − Restschuld), Näherung"},
            ]
        elif "t_ges" not in aus:
            t_ges = _tabelle(gs.rename(columns={"Anteil_Kontostand": "Anteil Kontostand", "Ausschuettung_Ist": "Ausschüttung Ist", "Ausschuettung_Plan": "Ausschüttung Plan",
                                                "Anteil_Massnahmen_offen": "Anteil offene Maßnahmen", "Anteil_Nettovermoegen": "Anteil Nettovermögen",
                                                "Nachschuss_Stress": "Nachschuss Stressfall", "Ausschuettung_Spielraum": "Ausschüttungsspielraum"}),
                             {"Quote": "pct", **{c: "eur" for c in ["Anteil Kontostand", "Ausschüttung Ist", "Ausschüttung Plan", "Anteil offene Maßnahmen", "Anteil Nettovermögen", "Nachschuss Stressfall", "Ausschüttungsspielraum"]}})

    ab = a.abstimmung.reset_index().rename(columns={"Monat": "Monat", "CF_netto": "Berechneter Netto-CF", "Kontostand": "Kontostand", "Abstimmung_Differenz": "Differenz zur Kontoveränderung"})
    ab["Monat"] = ab["Monat"].dt.strftime("%m/%Y")
    t_abst = _tabelle(ab, {"Berechneter Netto-CF": "eur", "Kontostand": "eur", "Differenz zur Kontoveränderung": "eur"})
    gl = pd.DataFrame([{"Kennzahl": x.titel, "Erklärung": x.erklaerung, "Formel": x.formel} for x in a.kpis.values()])
    t_gloss = _tabelle(gl, {})

    tabellen = {"t_monat": t_monat, "t_massn": t_massn, "t_obj": t_obj, "t_nutz": t_nutz, "t_szen": t_szen, "t_abst": t_abst, "t_gloss": t_gloss}
    tabellen = {k_: ("" if k_ in aus else v) for k_, v in tabellen.items()}
    kommentar = [html.escape(t) for tag, t in a.kommentar_t if tag in themen]
    env = Environment(autoescape=False)
    ctx = dict(css=CSS, titel=profil.titel, stand=f"{d.letzter_ist:%m/%Y}", ende=f"{d.monate[-1]:%m/%Y}", n_obj=len(d.objekte), erstellt=f"{datetime.now():%d.%m.%Y}",
               zielgruppe=html.escape(profil.zielgruppe), einleitung=html.escape(profil.einleitung), person=html.escape(person) if person else None,
               nav=[(x, ABSCHNITT_TITEL[x]) for x in abschnitte], tiles=mk(tiles), fin_tiles=mk(fin), sym=SYMBOL, kommentar=kommentar, fig=fig,
               t_ges=t_ges, person_tiles=person_tiles, stress=a.stress, eur=_eur, meldungen=[(s_, html.escape(t)) for s_, t in d.meldungen], **tabellen)
    teile = [env.from_string(HEAD).render(**ctx)]
    teile += [env.from_string(SECTIONS[x]).render(**ctx) for x in abschnitte]
    teile.append(FOOT)
    return "".join(teile)


def finde_browser() -> str | None:
    for n in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        if shutil.which(n):
            return shutil.which(n)
    for p in sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome")):
        return str(p)
    return None


def erzeuge_pdf(html_pfad: Path, pdf_pfad: Path) -> bool:
    b = finde_browser()
    if not b:
        return False
    cmd = [b, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf_pfad}",
           "--virtual-time-budget=15000", html_pfad.resolve().as_uri()]
    subprocess.run(cmd, check=False, capture_output=True, timeout=180)
    return pdf_pfad.exists()
