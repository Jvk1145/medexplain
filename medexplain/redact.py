"""Privacy: remove personal identifiers from report text BEFORE it is sent to the API.

Age and sex are kept because normal ranges depend on them.
"""
import re

# "Label : value" lines whose value is personal information.
_LABELS = (
    r"patient\s*name|name|mobile(?:\s*no)?|phone(?:\s*no)?|contact(?:\s*no)?|address|email|"
    r"uhid|patient\s*id|pid|mrn|lab\s*no|sample\s*id|barcode|ref(?:erred)?\.?\s*by|"
    r"referring\s*doctor|doctor|dr\.?|aadhaar|aadhar"
)
_LABEL_RE = re.compile(rf"(?im)^(\s*(?:{_LABELS})\s*[:\-]\s*)(.+)$")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
_AADHAAR_RE = re.compile(r"(?<!\d)\d{4}\s\d{4}\s\d{4}(?!\d)")


def redact(text: str) -> tuple[str, int]:
    """Return (redacted_text, number_of_redactions)."""
    count = 0

    def _sub(pattern, repl, s):
        nonlocal count
        s, n = pattern.subn(repl, s)
        count += n
        return s

    text = _sub(_LABEL_RE, r"\1[REDACTED]", text)
    text = _sub(_EMAIL_RE, "[EMAIL]", text)
    text = _sub(_AADHAAR_RE, "[ID]", text)
    text = _sub(_PHONE_RE, "[PHONE]", text)
    return text, count
