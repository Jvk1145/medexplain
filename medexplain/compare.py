"""'What changed?' between two reports – pure code, no AI needed."""
from .red_flags import _norm_name


def _distance(v, lo, hi) -> float:
    """How far a value is outside its normal range (0 = inside)."""
    if v is None:
        return 0.0
    if lo is not None and v < lo:
        return lo - v
    if hi is not None and v > hi:
        return v - hi
    return 0.0


def compare(old: dict, new: dict) -> dict:
    old_by = {_norm_name(t["name"]): t for t in old.get("tests", [])}
    out = {"improved": [], "worsened": [], "newly_abnormal": [], "back_to_normal": [], "unchanged": []}
    for t in new.get("tests", []):
        o = old_by.get(_norm_name(t["name"]))
        if not o or o.get("value") is None or t.get("value") is None:
            continue
        lo = t.get("ref_low") if t.get("ref_low") is not None else o.get("ref_low")
        hi = t.get("ref_high") if t.get("ref_high") is not None else o.get("ref_high")
        d_old, d_new = _distance(o["value"], lo, hi), _distance(t["value"], lo, hi)
        row = {"test": t["name"], "old": o["value"], "new": t["value"], "unit": t.get("unit", "")}
        if d_old > 0 and d_new == 0:
            out["back_to_normal"].append(row)
        elif d_old == 0 and d_new > 0:
            out["newly_abnormal"].append(row)
        elif d_new < d_old:
            out["improved"].append(row)
        elif d_new > d_old:
            out["worsened"].append(row)
        else:
            out["unchanged"].append(row)
    return out
