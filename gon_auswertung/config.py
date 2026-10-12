"""Parameter, Schwellenwerte und Szenario-Definitionen.

Alle Werte können im Excel-Blatt "Parameter" überschrieben werden.
"""
from __future__ import annotations

from dataclasses import dataclass

PARAMETER_DEFAULTS: dict[str, tuple[float, str]] = {
    "mindestliquiditaet": (100_000, "Mindest-Kontostand in € (Gesellschaftsvertrag / Bankauflage), solange keine Vorgabe existiert: interner Richtwert"),
    "dscr_gruen": (1.20, "DSCR ab diesem Wert = grün"),
    "dscr_gelb": (1.00, "DSCR ab diesem Wert = gelb, darunter rot"),
    "puffer_gruen_monate": (3.0, "Liquiditätspuffer (Monate Fixkosten + Kapitaldienst) ab diesem Wert = grün"),
    "puffer_gelb_monate": (1.5, "Liquiditätspuffer ab diesem Wert = gelb, darunter rot"),
    "ltv_gruen": (0.60, "Beleihungsauslauf bis zu diesem Wert = grün"),
    "ltv_gelb": (0.75, "Beleihungsauslauf bis zu diesem Wert = gelb, darüber rot"),
    "auslastung_gruen": (0.95, "Auslastung (Miete / Soll-Miete) ab diesem Wert = grün"),
    "auslastung_gelb": (0.90, "Auslastung ab diesem Wert = gelb, darunter rot"),
    "rueckstellung_gruen": (1.00, "Rückstellungsdeckung offener Maßnahmen ab diesem Wert = grün"),
    "rueckstellung_gelb": (0.60, "Rückstellungsdeckung ab diesem Wert = gelb, darunter rot"),
    "stress_leerstand": (0.05, "Pessimistisches Szenario: zusätzlicher Mietausfall (Anteil der Plan-Miete)"),
    "stress_zins_pp": (0.02, "Pessimistisches Szenario: Zinsanstieg in Prozentpunkten bei auslaufender Zinsbindung"),
    "sens_massnahmen_plus": (0.20, "Sensitivität: Kostensteigerung bei Maßnahmen"),
    "sens_fixkosten_plus": (0.05, "Sensitivität: Kostensteigerung Fixkosten"),
    "sens_miete_minus": (0.10, "Sensitivität: Mietrückgang"),
}


@dataclass(frozen=True)
class Spec:
    """Annahmen eines Szenarios für den Prognosezeitraum (Plan-Monate)."""

    name: str
    leerstand: float = 0.0          # zusätzlicher Mietausfall (Anteil)
    miete_faktor: float = 1.0
    fixk_faktor: float = 1.0
    zins_pp: float = 0.0            # Zinsaufschlag bei auslaufender Zinsbindung
    massnahmen_modus: str = "erwartet"   # min | erwartet | max
    massnahmen_faktor: float = 1.0


def szenarien(p: dict[str, float]) -> dict[str, Spec]:
    return {
        "Basis": Spec("Basis"),
        "Optimistisch": Spec("Optimistisch", massnahmen_modus="min"),
        "Pessimistisch": Spec(
            "Pessimistisch",
            leerstand=p["stress_leerstand"],
            zins_pp=p["stress_zins_pp"],
            massnahmen_modus="max",
        ),
    }
