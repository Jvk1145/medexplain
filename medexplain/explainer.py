"""Step 3: explanation + "connect the dots" pattern analysis + chat."""
import json

from .llm import call_tool, stream_text
from .prompts import CHAT_SYSTEM, EXPLAIN_SYSTEM, LEVELS

EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_summary": {"type": "string", "description": "3-5 sentence summary of the whole report"},
        "test_explanations": {
            "type": "array",
            "description": "One entry per abnormal test (high/low).",
            "items": {
                "type": "object",
                "properties": {
                    "test_name": {"type": "string"},
                    "what_it_is": {"type": "string"},
                    "what_your_result_means": {"type": "string"},
                },
                "required": ["test_name", "what_it_is", "what_your_result_means"],
            },
        },
        "patterns": {
            "type": "array",
            "description": "Connect-the-dots findings that combine 2+ tests.",
            "items": {
                "type": "object",
                "properties": {
                    "tests_involved": {"type": "array", "items": {"type": "string"}},
                    "observation": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                },
                "required": ["tests_involved", "observation", "why_it_matters"],
            },
        },
        "doctor_questions": {"type": "array", "items": {"type": "string"}},
        "lifestyle_tips": {"type": "array", "items": {"type": "string"},
                           "description": "General, safe food/activity tips. No medicines."},
    },
    "required": ["overall_summary", "test_explanations", "patterns", "doctor_questions", "lifestyle_tips"],
}


def _report_for_llm(report: dict) -> str:
    slim = {
        "age": report.get("age"), "sex": report.get("sex"),
        "tests": [{k: t.get(k) for k in ("name", "value", "value_text", "unit", "ref_text", "status")}
                  for t in report.get("tests", [])],
    }
    return json.dumps(slim, ensure_ascii=False, indent=1)


def explain(report: dict, alerts: list, level: str, language: str) -> dict:
    prompt = (
        f"Lab report data:\n{_report_for_llm(report)}\n\n"
        f"Critical alerts already detected by safety rules: {json.dumps(alerts, ensure_ascii=False)}\n\n"
        f"Explanation level: {LEVELS[level]}\n"
        f"Write ALL text in {language}. Keep test names in English in brackets if translating.\n"
        "Use the save_explanation tool."
    )
    return call_tool(EXPLAIN_SYSTEM, [{"type": "text", "text": prompt}], "save_explanation",
                     "Save the explanation of the lab report.", EXPLAIN_SCHEMA)


def chat_stream(report: dict, history: list, language: str):
    """Stream a chat answer. The report context is prompt-cached across turns."""
    system = [{
        "type": "text",
        "text": CHAT_SYSTEM + f"\nAlways reply in {language}.\n\nREPORT DATA:\n" + _report_for_llm(report),
        "cache_control": {"type": "ephemeral"},
    }]
    yield from stream_text(system, history, max_tokens=1000)
