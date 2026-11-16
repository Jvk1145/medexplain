"""Step 2: a SECOND AI call double-checks the extraction against the original.

A wrong number in medical data is dangerous, so the AI never silently guesses:
problems are shown to the user, who confirms or fixes the value.
"""
import json

from .llm import call_tool
from .prompts import VERIFY_SYSTEM

ISSUES_SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "test_name": {"type": "string"},
                    "problem": {"type": "string", "enum": [
                        "wrong_value", "wrong_unit", "wrong_range", "missing_test", "unreadable"]},
                    "extracted": {"type": "string"},
                    "suggested": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": ["test_name", "problem", "explanation"],
            },
        }
    },
    "required": ["issues"],
}


def verify(source_blocks: list, tests: list) -> list:
    slim = [{k: t.get(k) for k in ("name", "value", "value_text", "unit", "ref_low", "ref_high")}
            for t in tests]
    content = source_blocks + [{
        "type": "text",
        "text": "Extracted values to check:\n" + json.dumps(slim, ensure_ascii=False, indent=1),
    }]
    result = call_tool(VERIFY_SYSTEM, content, "report_issues",
                       "Report problems found in the extraction (empty list if none).",
                       ISSUES_SCHEMA, max_tokens=3000)
    issues = result.get("issues", [])
    # Also surface anything the extractor itself was unsure about.
    for t in tests:
        if t.get("confidence") == "low":
            issues.append({"test_name": t["name"], "problem": "unreadable",
                           "extracted": str(t.get("value_text", "")), "suggested": "",
                           "explanation": "The extractor was not confident reading this value."})
    return issues
