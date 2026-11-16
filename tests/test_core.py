"""Tests for the parts that must be deterministic: safety rules, privacy, status, comparison."""
from medexplain.compare import compare
from medexplain.extractor import compute_status
from medexplain.red_flags import check
from medexplain.redact import redact


def t(name, value, unit, lo=None, hi=None):
    return {"name": name, "value": value, "unit": unit, "ref_low": lo, "ref_high": hi}


# ── red flags ──
def test_critical_potassium_flagged():
    assert check([t("Serum Potassium", 6.8, "mmol/L")])


def test_normal_potassium_not_flagged():
    assert not check([t("Potassium", 4.2, "mmol/L")])


def test_hba1c_is_not_mistaken_for_hemoglobin():
    assert not check([t("Glycated Hemoglobin (HbA1c)", 6.5, "%")])


def test_low_hemoglobin_flagged():
    assert check([t("Hemoglobin (Hb)", 6.1, "g/dL")])


def test_platelets_in_lakh_units_converted():
    assert check([t("Platelet Count", 0.15, "lakh/cumm")])        # 15,000 -> critical
    assert not check([t("Platelet Count", 2.5, "lakh/cumm")])     # 2.5 lakh -> normal


def test_glucose_mmol_converted():
    assert check([t("Glucose Fasting", 2.0, "mmol/L")])           # 36 mg/dL


def test_unknown_unit_is_not_guessed():
    assert not check([t("Potassium", 999, "weird-unit")])


# ── privacy ──
def test_redact_removes_identity_keeps_age():
    text = "Patient Name : Rahul Sharma\nAge : 45 Years\nMobile: 9876543210\nUHID: AB12345\nHemoglobin 13.5 g/dL"
    clean, n = redact(text)
    assert "Rahul" not in clean and "9876543210" not in clean and "AB12345" not in clean
    assert "Age : 45" in clean and "Hemoglobin 13.5" in clean
    assert n >= 3


# ── status computed in code ──
def test_compute_status():
    assert compute_status(t("Hb", 10, "g/dL", 13, 17)) == "low"
    assert compute_status(t("Hb", 18, "g/dL", 13, 17)) == "high"
    assert compute_status(t("Hb", 14, "g/dL", 13, 17)) == "normal"
    assert compute_status({"value": None, "flag_on_report": "H"}) == "high"


# ── compare ──
def test_compare_reports():
    old = {"tests": [t("Vitamin D", 12, "ng/mL", 30, 100), t("LDL", 120, "mg/dL", None, 100)]}
    new = {"tests": [t("Vitamin D", 34, "ng/mL", 30, 100), t("LDL", 150, "mg/dL", None, 100)]}
    d = compare(old, new)
    assert d["back_to_normal"][0]["test"] == "Vitamin D"
    assert d["worsened"][0]["test"] == "LDL"
