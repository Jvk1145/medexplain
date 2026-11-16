"""Rule-based critical-value alerts.

Safety-critical decisions are NOT left to the AI: these thresholds are plain code,
so they are predictable and testable. The AI only explains.

Thresholds are adult critical ("panic") values of the kind commonly used by labs.
They are illustrative for this project and should be reviewed by a clinician
before any real-world use.
"""
import re

COUNT_UNITS = {  # multiplier -> converts to 10^3/uL
    "10^3/ul": 1, "x10^3/ul": 1, "10³/ul": 1, "x10³/ul": 1, "thou/ul": 1, "k/ul": 1,
    "10^9/l": 1, "x10^9/l": 1, "thou/cumm": 1, "10^3/cumm": 1,
    "/cumm": 0.001, "/ul": 0.001, "cells/cumm": 0.001, "/mm3": 0.001, "cells/ul": 0.001,
    "lakh/cumm": 100, "lakhs/cumm": 100, "lakh/ul": 100, "lakhs/ul": 100,
}

RULES = [
    {"test": "Potassium", "aliases": ["potassium", "k"], "exclude": [],
     "units": {"mmol/l": 1, "meq/l": 1}, "low": 2.8, "high": 6.2},
    {"test": "Sodium", "aliases": ["sodium", "na"], "exclude": [],
     "units": {"mmol/l": 1, "meq/l": 1}, "low": 120, "high": 160},
    {"test": "Glucose", "aliases": ["glucose", "bloodsugar", "sugar", "fbs", "rbs", "ppbs"],
     "exclude": ["urine"], "units": {"mg/dl": 1, "mmol/l": 18}, "low": 50, "high": 400},
    {"test": "Hemoglobin", "aliases": ["hemoglobin", "haemoglobin", "hb", "hgb"],
     "exclude": ["a1c", "glycated", "glycosylated"], "units": {"g/dl": 1, "g/l": 0.1, "gm/dl": 1, "gm%": 1},
     "low": 7, "high": 20},
    {"test": "Platelet count", "aliases": ["platelet", "plt"], "exclude": ["volume", "mpv", "pdw"],
     "units": COUNT_UNITS, "low": 20, "high": 1000},
    {"test": "White blood cell count",
     "aliases": ["wbc", "wbccount", "tlc", "leukocyte", "leucocyte", "whitebloodcell"],
     "exclude": [], "units": COUNT_UNITS, "low": 2, "high": 30},
    {"test": "Calcium", "aliases": ["calcium", "ca"], "exclude": ["ionized", "ionised", "urine"],
     "units": {"mg/dl": 1}, "low": 6.5, "high": 13},
]

_PREFIXES = ("serum", "plasma", "blood", "total")


def _norm_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9]", "", name.lower())
    for p in _PREFIXES:
        if s.startswith(p) and len(s) > len(p):
            s = s[len(p):]
    return s


def _norm_unit(unit: str) -> str:
    return (unit or "").lower().replace("µ", "u").replace("μ", "u").replace(" ", "")


def _match(rule, name: str) -> bool:
    n = _norm_name(name)
    if any(x in n for x in rule["exclude"]):
        return False
    for a in rule["aliases"]:
        # very short aliases (k, na, hb, ca) must match exactly to avoid false hits
        if (len(a) <= 3 and n == a) or (len(a) > 3 and n.startswith(a)):
            return True
    return False


def check(tests: list) -> list:
    """Return a list of critical alerts for values beyond panic thresholds."""
    alerts = []
    for t in tests:
        v = t.get("value")
        if v is None:
            continue
        for rule in RULES:
            if not _match(rule, t.get("name", "")):
                continue
            mult = rule["units"].get(_norm_unit(t.get("unit", "")))
            if mult is None:
                break  # unknown unit -> don't guess
            converted = v * mult
            if converted < rule["low"]:
                direction = "critically LOW"
            elif converted > rule["high"]:
                direction = "critically HIGH"
            else:
                break
            alerts.append({
                "test": t["name"], "value": v, "unit": t.get("unit", ""),
                "message": f"{t['name']} is {direction} ({v} {t.get('unit', '')}). "
                           "Please contact a doctor today.",
            })
            break
    return alerts
