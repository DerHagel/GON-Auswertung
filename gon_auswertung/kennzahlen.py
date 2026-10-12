"""Kennzahlen auf Gesellschafts-, Nutzungs- und Objektebene, Sensitivität, Textkommentar."""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from .config import Spec, szenarien
from .laden import Daten
from .modell import Ergebnis, min_kontostand, simuliere

GRUEN, GELB, ROT = "gruen", "gelb", "rot"
SYMBOL = {GRUEN: "●", GELB: "▲", ROT: "■"}      # Form + Farbe (nie Farbe allein)
TEXT = {GRUEN: "in Ordnung", GELB: "beobachten", ROT: "kritisch"}


def ampel(wert: float | None, gruen: float, gelb: float, hoeher_besser: bool = True) -> str | None:
    if wert is None or (isinstance(wert, float) and not np.isfinite(wert)):
        return None
    if hoeher_besser:
        return GRUEN if wert >= gruen else GELB if wert >= gelb else ROT
    return GRUEN if wert <= gruen else GELB if wert <= gelb else ROT


def _div(a: float, b: float) -> float:
    return float(a) / float(b) if b not in (0, 0.0) and pd.notna(b) else float("nan")


@dataclass
class Kpi:
    schluessel: str
    titel: str
    wert: float
    einheit: str            # eur | x | pct | mon
    status: str | None
    erklaerung: str
    formel: str


@dataclass
class Analyse:
    daten: Daten
    ergebnisse: dict[str, Ergebnis]
    kpis: dict[str, Kpi]
    objekt_kpis: pd.DataFrame
    nutzung_kpis: pd.DataFrame
    sensitivitaet: pd.DataFrame
    stress: dict[str, float]
    gesellschafter: pd.DataFrame
    kommentar: list[str]
    abstimmung: pd.DataFrame

    @property
    def basis(self) -> Ergebnis:
        return self.ergebnisse["Basis"]


# ----------------------------------------------------------------------------------------------
def objekt_kennzahlen(d: Daten, e: Ergebnis, monate: list[pd.Timestamp]) -> pd.DataFrame:
    p = d.params
    om = e.objekt_monat[e.objekt_monat["Monat"].isin(monate)]
    n = max(len(monate), 1)
    s = om.groupby("Objekt_ID").agg(
        Soll_Miete=("Soll_Miete", "sum"), Miete=("Miete_s", "sum"), Fixkosten=("Fixkosten_s", "sum"),
        Instandhaltung=("Instandhaltung", "sum"), Kapitaldienst=("Kapitaldienst", "sum"), Zins=("Zins_s", "sum"),
        NOI=("NOI", "sum"), CF_vor_Massnahmen=("CF_vor_Massnahmen", "sum"), Massnahmen=("Massnahmen", "sum"),
        Rueckstellung=("Rueckstellung_Bestand", "last"),
    )
    o = d.objekte.set_index("Objekt_ID")
    s = o[["Name", "Nutzung", "Flaeche_qm", "Verkehrswert", "Restschuld", "Zinssatz", "Zinsbindung_bis"]].join(s)
    s["Auslastung"] = s["Miete"] / s["Soll_Miete"].replace(0, np.nan)
    s["NOI_Marge"] = s["NOI"] / s["Miete"].replace(0, np.nan)
    s["DSCR"] = s["NOI"] / s["Kapitaldienst"].replace(0, np.nan)
    s["Kapitaldienstquote"] = s["Kapitaldienst"] / s["Miete"].replace(0, np.nan)
    s["LTV"] = s["Restschuld"] / s["Verkehrswert"].replace(0, np.nan)
    s["NOI_Rendite_pa"] = s["NOI"] * 12 / n / s["Verkehrswert"].replace(0, np.nan)
    s["Debt_Yield_pa"] = s["NOI"] * 12 / n / s["Restschuld"].replace(0, np.nan)
    s["IH_je_qm_pa"] = s["Instandhaltung"] * 12 / n / s["Flaeche_qm"].replace(0, np.nan)
    s["Miete_je_qm"] = s["Miete"] / n / s["Flaeche_qm"].replace(0, np.nan)
    s["Break_even_Auslastung"] = (s["Fixkosten"] + s["Instandhaltung"] + s["Kapitaldienst"]) / s["Soll_Miete"].replace(0, np.nan)
    s["Zinsbindung_Monate"] = ((s["Zinsbindung_bis"] - d.letzter_ist).dt.days / 30.4).round(0)
    s["Ampel_DSCR"] = [ampel(v, p["dscr_gruen"], p["dscr_gelb"]) for v in s["DSCR"]]
    s["Ampel_Auslastung"] = [ampel(v, p["auslastung_gruen"], p["auslastung_gelb"]) for v in s["Auslastung"]]
    s["Ampel_LTV"] = [ampel(v, p["ltv_gruen"], p["ltv_gelb"], hoeher_besser=False) for v in s["LTV"]]
    rang = {ROT: 2, GELB: 1, GRUEN: 0, None: 0}
    s["Risiko_Score"] = s[["Ampel_DSCR", "Ampel_Auslastung", "Ampel_LTV"]].apply(lambda r: sum(rang[x] for x in r), axis=1)
    return s.reset_index()


def nutzung_kennzahlen(ok: pd.DataFrame) -> pd.DataFrame:
    g = ok.groupby("Nutzung").agg(
        Objekte=("Objekt_ID", "count"), Flaeche_qm=("Flaeche_qm", "sum"), Verkehrswert=("Verkehrswert", "sum"),
        Restschuld=("Restschuld", "sum"), Soll_Miete=("Soll_Miete", "sum"), Miete=("Miete", "sum"),
        Fixkosten=("Fixkosten", "sum"), Instandhaltung=("Instandhaltung", "sum"),
        Kapitaldienst=("Kapitaldienst", "sum"), NOI=("NOI", "sum"), Massnahmen=("Massnahmen", "sum"),
    )
    g["Auslastung"] = g["Miete"] / g["Soll_Miete"]
    g["NOI_Marge"] = g["NOI"] / g["Miete"]
    g["DSCR"] = g["NOI"] / g["Kapitaldienst"]
    g["LTV"] = g["Restschuld"] / g["Verkehrswert"]
    return g.reset_index()


# ----------------------------------------------------------------------------------------------
def _gesellschaft_kpis(d: Daten, erg: dict[str, Ergebnis]) -> dict[str, Kpi]:
    p = d.params
    base = erg["Basis"]
    g = base.monat
    ist = g[g["Typ"] == "Ist"]
    plan = g[g["Typ"] == "Plan"]
    obj = d.objekte
    kpis: dict[str, Kpi] = {}

    def add(k, titel, wert, einheit, status, erkl, formel):
        kpis[k] = Kpi(k, titel, wert, einheit, status, erkl, formel)

    ks = float(g.loc[d.letzter_ist, "Kontostand"])
    add("kontostand", "Kontostand (letzter Ist-Monat)", ks, "eur", ampel(ks, p["mindestliquiditaet"] * 1.5, p["mindestliquiditaet"]),
        "Verfügbare Liquidität am Ende des letzten Ist-Monats. Rückstellungen sind aktuell nur bilanziell und nicht durch Geld hinterlegt – der Kontostand ist daher die freie Liquidität.",
        "Kontostand laut Konto")

    for name, e in erg.items():
        mn, wann = min_kontostand(e)
        if name == "Basis":
            add("min_basis", "Tiefster Kontostand Prognose (Basis)", mn, "eur", ampel(mn, p["mindestliquiditaet"] * 1.5, p["mindestliquiditaet"]),
                f"Engpass im Prognosezeitraum ({wann:%m/%Y}) mit erwarteten Maßnahmenkosten.", "min(Kontostand) über Plan-Monate")
        if name == "Pessimistisch":
            add("min_pess", "Tiefster Kontostand (pessimistisch)", mn, "eur", ampel(mn, p["mindestliquiditaet"] * 1.5, p["mindestliquiditaet"]),
                f"Stressfall ({wann:%m/%Y}): Maßnahmen zu Maximalkosten, {p['stress_leerstand']:.0%} Mietausfall, +{p['stress_zins_pp'] * 100:.1f} Pp. Zins bei auslaufender Bindung.",
                "min(Kontostand) im Szenario Pessimistisch")

    fix_kd_ih = ist["Fixkosten"] + ist["Kapitaldienst"] + ist["Instandhaltung"]
    puffer = _div(ks, fix_kd_ih.mean())
    add("puffer", "Liquiditätspuffer (Monate)", puffer, "mon", ampel(puffer, p["puffer_gruen_monate"], p["puffer_gelb_monate"]),
        "Wie viele Monate laufende Kosten (Fixkosten, Kapitaldienst, Instandhaltung) der Kontostand abdecken würde – ganz ohne Mieteinnahmen.",
        "Kontostand ÷ Ø monatliche (Fixkosten + Kapitaldienst + Instandhaltung)")

    dscr_ist = _div(ist["NOI"].sum(), ist["Kapitaldienst"].sum())
    add("dscr_ist", "DSCR Ist", dscr_ist, "x", ampel(dscr_ist, p["dscr_gruen"], p["dscr_gelb"]),
        "Kapitaldienstdeckung: Das Vielfache, mit dem das Betriebsergebnis Zins und Tilgung deckt. Bankenkennzahl Nr. 1.",
        "NOI ÷ (Zins + Tilgung)")
    dscr_pl = _div(plan["NOI"].sum(), plan["Kapitaldienst"].sum()) if len(plan) else float("nan")
    add("dscr_plan", "DSCR Prognose", dscr_pl, "x", ampel(dscr_pl, p["dscr_gruen"], p["dscr_gelb"]),
        "DSCR der Plan-Monate (Basisszenario).", "NOI ÷ Kapitaldienst, Plan-Monate")
    miete = ist["Miete"].sum()
    add("auslastung", "Mietauslastung", _div(miete, ist["Soll_Miete"].sum()), "pct",
        ampel(_div(miete, ist["Soll_Miete"].sum()), p["auslastung_gruen"], p["auslastung_gelb"]),
        "Anteil der Soll-Miete (Vollvermietung), der tatsächlich eingeht – bildet Leerstand und Ausfälle ab.", "Ist-Miete ÷ Soll-Miete")
    add("kd_quote", "Kapitaldienstquote", _div(ist["Kapitaldienst"].sum(), miete), "pct", None,
        "Anteil der Miete, der an die Banken geht.", "(Zins + Tilgung) ÷ Miete")
    add("fix_quote", "Kostenquote (ohne Kapitaldienst)", _div(ist["Fixkosten"].sum() + ist["Instandhaltung"].sum(), miete), "pct", None,
        "Anteil der Miete, den Bewirtschaftung und Instandhaltung verbrauchen.", "(Fixkosten + Instandhaltung) ÷ Miete")
    add("noi_marge", "NOI-Marge", _div(ist["NOI"].sum(), miete), "pct", None,
        "Was von der Miete nach Bewirtschaftung übrig bleibt – vor Kapitaldienst.", "NOI ÷ Miete")
    be = _div(ist["Fixkosten"].sum() + ist["Instandhaltung"].sum() + ist["Kapitaldienst"].sum(), ist["Soll_Miete"].sum())
    add("break_even", "Break-even-Auslastung", be, "pct", None,
        "Auslastung, ab der alle laufenden Kosten inkl. Kapitaldienst gedeckt sind. Je niedriger, desto robuster.",
        "(Fixkosten + Instandhaltung + Kapitaldienst) ÷ Soll-Miete")

    vw, rs = obj["Verkehrswert"].sum(), obj["Restschuld"].sum()
    ltv = _div(rs, vw)
    add("ltv", "Beleihungsauslauf (LTV)", ltv, "pct", ampel(ltv, p["ltv_gruen"], p["ltv_gelb"], hoeher_besser=False),
        "Restschuld im Verhältnis zum Verkehrswert – zentrale Größe für Anschlussfinanzierungen.", "Restschuld ÷ Verkehrswert")
    n = max(len(ist), 1)
    noi_pa = ist["NOI"].sum() * 12 / n
    add("debt_yield", "Debt Yield", _div(noi_pa, rs), "pct", None,
        "Jahres-NOI im Verhältnis zur Restschuld – finanzierungsunabhängiges Tragfähigkeitsmaß der Banken.", "NOI p. a. ÷ Restschuld")
    add("noi_rendite", "NOI-Rendite auf Verkehrswert", _div(noi_pa, vw), "pct", None,
        "Ertragskraft des Portfolios bezogen auf den Marktwert.", "NOI p. a. ÷ Verkehrswert")
    nav = vw - rs
    cf_pa = ist["CF_vor_Massnahmen"].sum() * 12 / n
    add("cf_rendite", "Cashflow-Rendite auf Nettovermögen", _div(cf_pa, nav), "pct", None,
        "Jahres-Cashflow nach Kapitaldienst im Verhältnis zu Verkehrswert abzüglich Restschuld (Näherung für das eingesetzte Eigenkapital).",
        "(NOI − Kapitaldienst) p. a. ÷ (Verkehrswert − Restschuld)")
    add("cf_ist", "Ø Monats-Cashflow vor Maßnahmen (Ist)", float(ist["CF_vor_Massnahmen"].mean()), "eur", None,
        "Durchschnittlicher monatlicher Überschuss nach Kapitaldienst, vor Sondermaßnahmen.", "NOI − Kapitaldienst")

    # Maßnahmen & Rückstellungen
    mk = base.massnahmen
    offen = mk[(mk["Monat"] > d.letzter_ist) & ~mk["Status"].isin(["entfallen", "abgeschlossen"])] if len(mk) else mk
    offen_summe = float(offen["Kosten_erwartet"].sum()) if len(offen) else 0.0
    offen_max = float(offen["Kosten_max"].sum()) if len(offen) else 0.0
    rueck = float(g.loc[d.letzter_ist, "Rueckstellung_Bestand"]) if pd.notna(g.loc[d.letzter_ist, "Rueckstellung_Bestand"]) else 0.0
    add("massn_offen", "Offene Maßnahmen (erwartet)", offen_summe, "eur", None,
        f"Summe der noch nicht abgeschlossenen Maßnahmen im Prognosezeitraum (Maximalkosten: {offen_max:,.0f} €).".replace(",", "."), "Σ Kosten_erwartet")
    rd = _div(rueck, offen_summe) if offen_summe > 0 else float("nan")
    add("rueck_deckung", "Rückstellungsdeckung offener Maßnahmen", rd, "pct", ampel(rd, p["rueckstellung_gruen"], p["rueckstellung_gelb"]),
        "Rückstellungsbestand im Verhältnis zu den offenen Maßnahmen (bilanzielle Vorsorge).", "Rückstellungen ÷ offene Maßnahmen")
    kd = _div(ks, offen_summe) if offen_summe > 0 else float("nan")
    add("kassen_deckung", "Liquiditätsdeckung offener Maßnahmen", kd, "pct", ampel(kd, 1.5, 1.0),
        "Wie viel der offenen Maßnahmen heute allein aus dem Kontostand bezahlbar wäre. Ehrlicher als die Rückstellungsdeckung, solange Rückstellungen nicht hinterlegt sind.",
        "Kontostand ÷ offene Maßnahmen")
    add("rueckstellung", "Rückstellungsbestand (bilanziell)", rueck, "eur", None, "Bestand laut Bilanz, nicht liquiditätswirksam.", "Σ Rückstellung_Bestand")
    add("ih_qm", "Instandhaltung je m² p. a.", _div(ist["Instandhaltung"].sum() * 12 / n, obj["Flaeche_qm"].sum()), "eur", None,
        "Laufende Instandhaltung bezogen auf die Gesamtfläche (Benchmark meist 8–15 €/m²).", "Instandhaltung p. a. ÷ Fläche")
    return kpis


def _sensitivitaet(d: Daten, base_min: float) -> pd.DataFrame:
    p = d.params
    fälle = [
        (f"Miete ±{p['sens_miete_minus']:.0%}", f"−{p['sens_miete_minus']:.0%} Miete", Spec("s", miete_faktor=1 - p["sens_miete_minus"]), f"Miete +{p['sens_miete_minus']:.0%}", Spec("s", miete_faktor=1 + p["sens_miete_minus"])),
        (f"Fixkosten ±{p['sens_fixkosten_plus']:.0%}", f"+{p['sens_fixkosten_plus']:.0%} Fixkosten", Spec("s", fixk_faktor=1 + p["sens_fixkosten_plus"]), f"−{p['sens_fixkosten_plus']:.0%} Fixkosten", Spec("s", fixk_faktor=1 - p["sens_fixkosten_plus"])),
        ("Zinsen bei Zinsbindungsende", f"+{p['stress_zins_pp'] * 100:.1f} Pp. Zins", Spec("s", zins_pp=p["stress_zins_pp"]), "−1 Pp. Zins", Spec("s", zins_pp=-0.01)),
        ("Maßnahmen: Min-/Max-Kosten", "Maximalkosten", Spec("s", massnahmen_modus="max"), "Minimalkosten", Spec("s", massnahmen_modus="min")),
        (f"Maßnahmen ±{p['sens_massnahmen_plus']:.0%}", f"Maßnahmen +{p['sens_massnahmen_plus']:.0%}", Spec("s", massnahmen_faktor=1 + p["sens_massnahmen_plus"]), f"Maßnahmen −{p['sens_massnahmen_plus']:.0%}", Spec("s", massnahmen_faktor=1 - p["sens_massnahmen_plus"])),
        ("Zusätzlicher Mietausfall", f"+{p['stress_leerstand']:.0%} Mietausfall", Spec("s", leerstand=p["stress_leerstand"]), "Kein zusätzl. Ausfall", Spec("s")),
    ]
    zeilen = []
    for name, neg_lbl, neg, pos_lbl, pos in fälle:
        mn_neg, _ = min_kontostand(simuliere(d, neg))
        mn_pos, _ = min_kontostand(simuliere(d, pos))
        zeilen.append({"Faktor": name, "Schlecht_Label": neg_lbl, "Delta_schlecht": mn_neg - base_min,
                       "Gut_Label": pos_lbl, "Delta_gut": mn_pos - base_min})
    t = pd.DataFrame(zeilen)
    t["Spannweite"] = t["Delta_gut"].abs() + t["Delta_schlecht"].abs()
    return t.sort_values("Spannweite", ascending=False).reset_index(drop=True)


def _break_even_leerstand(d: Daten, ziel: float) -> float:
    """Zusätzlicher Mietausfall, bei dem der tiefste Kontostand gerade die Mindestliquidität erreicht."""
    lo, hi = 0.0, 1.0
    if min_kontostand(simuliere(d, Spec("x", leerstand=0.0)))[0] < ziel:
        return 0.0
    if min_kontostand(simuliere(d, Spec("x", leerstand=hi)))[0] >= ziel:
        return 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if min_kontostand(simuliere(d, Spec("x", leerstand=mid)))[0] >= ziel:
            lo = mid
        else:
            hi = mid
    return lo


def _gesellschafter(d: Daten, nachschuss: float, ausschuettung_max: float) -> pd.DataFrame:
    if d.gesellschafter.empty:
        return pd.DataFrame()
    t = d.gesellschafter.copy()
    t["Nachschuss_Stress"] = t["Quote"] * nachschuss
    t["Ausschuettung_Spielraum"] = t["Quote"] * ausschuettung_max
    return t


def _kommentar(d: Daten, kpis: dict[str, Kpi], erg: dict[str, Ergebnis], stress: dict, ok: pd.DataFrame) -> list[str]:
    p = d.params
    eur = lambda x: f"{x:,.0f} €".replace(",", ".")
    dz = lambda x, n=2: f"{x:.{n}f}".replace(".", ",")
    s = []
    k = kpis
    mb, wb = min_kontostand(erg["Basis"])
    mp, wp = min_kontostand(erg["Pessimistisch"])
    s.append(f"Der Kontostand beträgt {eur(k['kontostand'].wert)} (Stand {d.letzter_ist:%m/%Y}), entsprechend {dz(k['puffer'].wert, 1)} Monaten laufender Kosten.")
    if mb >= p["mindestliquiditaet"]:
        s.append(f"Im Basisszenario sinkt die Liquidität bis {d.monate[-1]:%m/%Y} auf mindestens {eur(mb)} ({wb:%m/%Y}) und bleibt über der Mindestliquidität von {eur(p['mindestliquiditaet'])}.")
    else:
        s.append(f"Im Basisszenario unterschreitet die Liquidität im {wb:%m/%Y} die Mindestliquidität von {eur(p['mindestliquiditaet'])} (Tiefpunkt {eur(mb)}).")
    if mp < p["mindestliquiditaet"]:
        s.append(f"Im Stressfall fällt der Kontostand bis {wp:%m/%Y} auf {eur(mp)}; es entstünde ein Nachschussbedarf von {eur(stress['nachschuss'])}.")
    else:
        s.append(f"Auch im Stressfall bleibt die Liquidität mit mindestens {eur(mp)} über der Mindestliquidität.")
    s.append(f"Die Kapitaldienstdeckung (DSCR) liegt bei {dz(k['dscr_ist'].wert)} ({TEXT.get(k['dscr_ist'].status, '')}); der Mietertrag trägt die Finanzierung bis zu einem Absinken der Auslastung auf {k['break_even'].wert:.0%} (aktuell {k['auslastung'].wert:.0%}).")
    kritisch = ok[ok["Ampel_DSCR"] == ROT]
    if len(kritisch):
        s.append(f"{len(kritisch)} von {len(ok)} Objekten haben einen DSCR unter {dz(p['dscr_gelb'])}: " + ", ".join(kritisch.nsmallest(5, "DSCR")["Name"]) + ("." if len(kritisch) <= 5 else " u. a."))
    if k["massn_offen"].wert > 0:
        s.append(f"Offene Maßnahmen von {eur(k['massn_offen'].wert)} stehen an; bilanzielle Rückstellungen decken {k['rueckstellung'].wert / k['massn_offen'].wert:.0%} davon, der Kontostand allein {k['kassen_deckung'].wert:.0%}.")
    be = stress["leerstand_be"]
    if 0 < be < 1:
        s.append(f"Zusätzlicher Mietausfall von bis zu {dz(be * 100, 1)} % würde die Mindestliquidität im Prognosezeitraum noch nicht gefährden.")
    elif be == 0:
        s.append("Schon ohne zusätzlichen Mietausfall wird die Mindestliquidität unterschritten.")
    bald = ok[(ok["Zinsbindung_Monate"].notna()) & (ok["Zinsbindung_Monate"] <= 12)]
    if len(bald):
        s.append(f"{len(bald)} Darlehen (Restschuld {eur(bald['Restschuld'].sum())}) laufen innerhalb von 12 Monaten aus der Zinsbindung – Anschlussfinanzierung vorbereiten.")
    return s


def analysieren(d: Daten) -> Analyse:
    sz = szenarien(d.params)
    erg = {name: simuliere(d, spec) for name, spec in sz.items()}
    kpis = _gesellschaft_kpis(d, erg)
    ok = objekt_kennzahlen(d, erg["Basis"], d.ist_monate)
    nk = nutzung_kennzahlen(ok)
    mb, _ = min_kontostand(erg["Basis"])
    mp, _ = min_kontostand(erg["Pessimistisch"])
    ziel = d.params["mindestliquiditaet"]
    stress = {
        "nachschuss": max(0.0, ziel - mp),
        "ausschuettung_max": max(0.0, mp - ziel),
        "leerstand_be": _break_even_leerstand(d, ziel),
    }
    sens = _sensitivitaet(d, mb)
    ges = _gesellschafter(d, stress["nachschuss"], stress["ausschuettung_max"])
    kom = _kommentar(d, kpis, erg, stress, ok)
    ab = erg["Basis"].monat.loc[erg["Basis"].monat["Typ"] == "Ist", ["CF_netto", "Kontostand", "Abstimmung_Differenz"]].copy()
    toleranz = max(1000.0, 0.01 * float(erg["Basis"].monat["Miete"].mean()))
    gross = ab["Abstimmung_Differenz"].abs() > toleranz
    if gross.any():
        d.meldungen.append(("warn", "Kontoabstimmung: berechneter Cashflow weicht von der Kontoveränderung ab in " + ", ".join(f"{m:%m/%Y} ({v:,.0f} €)".replace(",", ".") for m, v in ab.loc[gross, "Abstimmung_Differenz"].items()) + " – fehlen Buchungen (z. B. Steuern, Darlehens­sondertilgung)?"))
    return Analyse(d, erg, kpis, ok, nk, sens, stress, ges, kom, ab)
