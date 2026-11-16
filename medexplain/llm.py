"""AI wrapper used by every module – free/cheap providers with fast automatic failover.

Providers (all use the OpenAI-compatible API, so one code path):
  • Gemini  – GEMINI_API_KEY_1.._9  (free: aistudio.google.com)
  • Groq    – GROQ_API_KEY_1.._9    (free: console.groq.com, very fast Llama models)
  • xAI Grok– XAI_API_KEY_1.._9     (paid: console.x.ai) – optional

Every key × model is a "slot". A slot gets 7 seconds (AI_TIMEOUT) to start answering;
if it is slow, rate-limited, invalid or erroring, the next slot is tried immediately and
the failing slot is rested for 60 s. If every slot fails, one last round runs with a longer
timeout so the report still comes through.
"""
import itertools
import json
import os
import re
import threading
import time

import httpx
import openai
from dotenv import load_dotenv

load_dotenv()

FAST_TIMEOUT = float(os.getenv("AI_TIMEOUT", "7"))   # seconds to wait before switching key
LAST_CHANCE_TIMEOUT = 45.0                           # final round if everything was slow
COOLDOWN = 60.0                                      # rest a failing slot for this long

PROVIDERS = {
    "gemini": {"label": "Gemini", "env": "GEMINI_API_KEY", "model_env": "GEMINI_MODEL",
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
               "models": "gemini-3.5-flash-lite,gemini-3.1-flash-lite", "json_stream": True},
    "groq": {"label": "Groq", "env": "GROQ_API_KEY", "model_env": "GROQ_MODEL",
             "base_url": "https://api.groq.com/openai/v1",
             "models": "qwen/qwen3.8-27b,openai/gpt-oss-120b", "json_stream": False},
    "xai": {"label": "Grok (xAI)", "env": "XAI_API_KEY", "model_env": "XAI_MODEL",
            "base_url": "https://api.x.ai/v1", "models": "grok-4-fast", "json_stream": True},
}
ORDER = [p.strip() for p in os.getenv("AI_ORDER", "gemini,groq,xai").split(",") if p.strip() in PROVIDERS]


class LLMError(Exception):
    """Raised when every slot failed. kind: 'auth' | 'rate' | 'other'."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def _load_keys(prefix: str) -> list[str]:
    raw = [os.getenv(prefix, "")] + [os.getenv(f"{prefix}_{i}", "") for i in range(1, 10)]
    out = []
    for k in (k.strip() for k in raw):
        if k and k not in out and not k.startswith("your-key"):
            out.append(k)
    return out


_timeout = httpx.Timeout(FAST_TIMEOUT, connect=FAST_TIMEOUT, write=30.0)
SLOTS = []  # dicts: provider, label, client, model
COUNTS = {}
for _p in ORDER:
    cfg = PROVIDERS[_p]
    keys = _load_keys(cfg["env"])
    COUNTS[cfg["label"]] = len(keys)
    models = [m.strip() for m in os.getenv(cfg["model_env"], cfg["models"]).split(",") if m.strip()]
    for _k in keys:
        _client = openai.OpenAI(api_key=_k, base_url=cfg["base_url"], max_retries=0, timeout=_timeout)
        for _m in models:
            SLOTS.append({"provider": _p, "label": cfg["label"], "client": _client, "model": _m,
                          "json_stream": cfg["json_stream"]})

_lock = threading.Lock()
_counter = itertools.count()
_rest_until = [0.0] * len(SLOTS)


def key_count() -> int:
    return sum(COUNTS.values())


def provider_name() -> str:
    return " + ".join(f"{name} ({n})" for name, n in COUNTS.items() if n) or "AI"


def _ordered_slots() -> list[int]:
    """Healthy slots first (rotating start to spread load), rested slots last."""
    if not SLOTS:
        raise LLMError("auth", "No AI key found. Add GEMINI_API_KEY_1 or GROQ_API_KEY_1 to your .env file.")
    with _lock:
        start = next(_counter) % len(SLOTS)
    idx = list(range(start, len(SLOTS))) + list(range(start))
    now = time.time()
    return [i for i in idx if _rest_until[i] <= now] + [i for i in idx if _rest_until[i] > now]


def _classify(e: Exception) -> str:
    if isinstance(e, openai.RateLimitError):
        return "rate"
    if isinstance(e, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return "auth"
    return "other"


def _run(attempt, rounds=((FAST_TIMEOUT,), (LAST_CHANCE_TIMEOUT,))):
    """Call attempt(slot, timeout) on each slot until one succeeds."""
    kinds, errors = [], []
    for (timeout,) in rounds:  # round 1: 7 s per slot; round 2: last chance, longer wait
        for i in _ordered_slots():
            slot = SLOTS[i]
            try:
                result = attempt(slot, timeout)
                _rest_until[i] = 0.0
                return result
            except Exception as e:  # noqa: BLE001 – any failure -> try the next slot
                _rest_until[i] = time.time() + COOLDOWN
                kinds.append(_classify(e))
                errors.append(f"{slot['label']}/{slot['model']}: {type(e).__name__}")
        if kinds and all(k == "auth" for k in kinds):
            break  # bad keys won't get better with a longer timeout
    kind = "rate" if "rate" in kinds else ("auth" if all(k == "auth" for k in kinds) else "other")
    raise LLMError(kind, "All AI keys failed – " + "; ".join(errors[-6:]))


# ───────────────────────── message conversion ─────────────────────────
def _system_text(system) -> str:
    return system if isinstance(system, str) else "\n".join(b.get("text", "") for b in system)


def _parts(content):
    """Our content blocks -> OpenAI-style content parts."""
    if isinstance(content, str):
        return content
    parts = []
    for b in content:
        if b["type"] == "text":
            parts.append({"type": "text", "text": b["text"]})
        elif b["type"] == "image":
            src = b["source"]
            parts.append({"type": "image_url",
                          "image_url": {"url": f"data:{src['media_type']};base64,{src['data']}"}})
    if all(p["type"] == "text" for p in parts):  # text-only models need a plain string
        return "\n\n".join(p["text"] for p in parts)
    return parts


def _parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("AI did not return JSON")
    return json.loads(text[start:end + 1])


def _default(s: dict):
    t = s.get("type")
    if isinstance(t, list):
        return None if "null" in t else _default({**s, "type": t[0]})
    if t == "object":
        return _fill({}, s)
    if t == "array":
        return []
    if t == "string":
        return s["enum"][-1] if "enum" in s else ""
    if t == "boolean":
        return False
    return None


def _fill(data, s: dict):
    """Make sure every field the app expects exists, even if the AI skipped it."""
    t = s.get("type")
    if isinstance(t, list):
        if data is None:
            return None
        t = next((x for x in t if x != "null"), None)
    if t == "object":
        data = data if isinstance(data, dict) else {}
        for k, sub in s.get("properties", {}).items():
            data[k] = _fill(data[k], sub) if k in data else _default(sub)
        return data
    if t == "array":
        data = data if isinstance(data, list) else []
        return [_fill(x, s.get("items", {})) for x in data]
    if t == "number" and isinstance(data, str):
        try:
            return float(data)
        except ValueError:
            return None
    return data


# ───────────────────────── public API ─────────────────────────
def call_tool(system, content, tool_name, description, schema, max_tokens=8000) -> dict:
    """Get structured JSON matching `schema` (tool_name/description describe the task)."""
    sys = (_system_text(system) +
           f"\n\nYour answer is the input of the function `{tool_name}`: {description}\n"
           "Respond with ONLY one JSON object (no markdown, no extra text) that follows this "
           "JSON schema exactly:\n" + json.dumps(schema, ensure_ascii=False))
    messages = [{"role": "system", "content": sys}, {"role": "user", "content": _parts(content)}]

    def attempt(slot, timeout):
        client = slot["client"].with_options(timeout=httpx.Timeout(timeout, connect=timeout, write=30.0))
        kw = {"response_format": {"type": "json_object"}} if slot["json_stream"] else {}
        stream = client.chat.completions.create(model=slot["model"], messages=messages,
                                                max_tokens=max_tokens, stream=True, **kw)
        text = "".join((ch.choices[0].delta.content or "") for ch in stream if ch.choices)
        return _fill(_parse_json(text), schema)

    return _run(attempt)


def stream_text(system, messages, max_tokens=1000):
    """Yield a streamed chat answer. Switches key only before the first word arrives."""
    msgs = [{"role": "system", "content": _system_text(system)}] + [
        {"role": m["role"], "content": _parts(m["content"])} for m in messages]

    def attempt(slot, timeout):
        client = slot["client"].with_options(timeout=httpx.Timeout(timeout, connect=timeout, write=30.0))
        stream = client.chat.completions.create(model=slot["model"], messages=msgs,
                                                max_tokens=max_tokens, stream=True)
        it = iter(stream)
        first = None
        for ch in it:  # wait for the first real text (failover still allowed here)
            if ch.choices and ch.choices[0].delta.content:
                first = ch.choices[0].delta.content
                break
        if first is None:
            raise ValueError("empty answer")
        return first, it

    first, it = _run(attempt)
    yield first
    try:
        for ch in it:
            if ch.choices and ch.choices[0].delta.content:
                yield ch.choices[0].delta.content
    except Exception:  # noqa: BLE001 – connection dropped mid-answer
        yield "\n\n_(The answer was cut off – please ask again.)_"
