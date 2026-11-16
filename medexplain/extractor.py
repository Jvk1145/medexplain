"""Step 1: report -> structured JSON (via forced tool call)."""
from .llm import call_tool
from .prompts import EXTRACT_SYSTEM

TEST_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Test name as printed, e.g. 'Hemoglobin'"},
        "section": {"type": "string", "description": "Panel, e.g. 'Complete Blood Count'"},
        "value": {"type": ["number", "null"]},
        "value_text": {"type": "string", "description": "Result exactly as printed"},
        "unit": {"type": "string"},
        "ref_low": {"type": ["number", "null"]},
        "ref_high": {"type": ["number", "null"]},
        "ref_text": {"type": "string", "description": "Reference range exactly as printed"},
        "flag_on_report": {"type": "string", "description": "H/L/High/Low flag if printed, else ''"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["name", "value", "value_text", "unit", "ref_low", "ref_high", "confidence"],
}

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "lab_name": {"type": "string"},
        "report_date": {"type": "string", "description": "YYYY-MM-DD if possible, else ''"},
        "age": {"type": ["number", "null"]},
        "sex": {"type": "string", "enum": ["male", "female", "unknown"]},
        "tests": {"type": "array", "items": TEST_SCHEMA},
    },
    "required": ["tests", "sex"],
}


def compute_status(t: dict) -> str:
    """Status is computed in CODE from the printed range – not guessed by the AI."""
    v, lo, hi = t.get("value"), t.get("ref_low"), t.get("ref_high")
    if v is None:
        flag = (t.get("flag_on_report") or "").lower()
        if flag.startswith("h"):
            return "high"
        if flag.startswith("l"):
            return "low"
        return "unknown"
    if lo is not None and v < lo:
        return "low"
    if hi is not None and v > hi:
        return "high"
    if lo is not None or hi is not None:
        return "normal"
    return "unknown"


def extract(source_blocks: list) -> dict:
    content = source_blocks + [{
        "type": "text",
        "text": "Extract all lab results from this report using the save_report_values tool.",
    }]
    report = call_tool(
        EXTRACT_SYSTEM, content, "save_report_values",
        "Save the structured lab values extracted from the report.", REPORT_SCHEMA,
    )
    for t in report.get("tests", []):
        t["status"] = compute_status(t)
    return report
