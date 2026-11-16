"""Voice explanation for elderly users (Google Text-to-Speech, needs internet)."""
import io

LANG_CODES = {"English": "en", "Hindi": "hi", "Marathi": "mr", "Tamil": "ta", "Telugu": "te",
              "Bengali": "bn", "Gujarati": "gu", "Kannada": "kn", "Malayalam": "ml"}


def speak(text: str, language: str) -> bytes | None:
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        gTTS(text=text, lang=LANG_CODES.get(language, "en")).write_to_fp(buf)
        return buf.getvalue()
    except Exception:
        return None
