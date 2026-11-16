# 🩺 MedExplain – AI Lab Report Explainer Agent

> Turns confusing lab reports into simple explanations in your own language. It finds patterns across tests, tracks your health over time and flags emergencies, with safety and privacy built in from day one.

Built with **Python, Claude (Anthropic API), Streamlit, SQLite**.

## ✨ What makes it different

| Feature | How it works |
|---|---|
| 🧠 **Connect-the-dots analysis** | Reads the report as *patterns* the way doctors do (e.g. low Hb + low MCV + low ferritin), not one number at a time |
| 🔍 **Self-verification** | A 2nd Claude call re-checks every extracted value against the original. Doubtful values are shown to the user to confirm, so the AI never silently guesses |
| 🚨 **Rule-based red flags** | Critical values (potassium, sodium, glucose, Hb, platelets, WBC, calcium) are checked by **plain code, not AI**: predictable and unit-tested |
| 🧪 **Status computed in code** | High/Low/Normal is calculated from the range **printed on that lab's report**, not guessed by the model |
| 🔒 **Privacy-first** | For text PDFs, name, phone, IDs and doctor are **redacted locally before anything is sent** to the API. One-click delete per profile |
| 🎚️ **Explanation levels** | Simple (for grandparents) / Detailed / Medical (for students) |
| 🌐 **9 Indian languages + 🔊 voice** | Explanations in Hindi, Marathi, Tamil… and read aloud for elderly users |
| 📈 **History & "What changed?"** | Saves reports per family member, plots trends against the normal band, compares two reports (back to normal / improved / worse) |
| 💬 **Chat with your report** | Streaming answers, report context prompt-cached across turns |

## 🏗️ Architecture

```
Upload (PDF / photo)
   │
   ▼
source.py ── text PDF? ──► extract text ► redact.py (remove PII) ► send TEXT only
   │            scanned? ──► send PDF document (Claude vision)
   │            photo?   ──► resize ► send image (Claude vision)
   ▼
extractor.py   Claude + forced tool call ► structured JSON  ► status computed in code
   ▼
verifier.py    2nd Claude call checks values  ► user confirms/edits in a table
   ▼
red_flags.py   deterministic critical-value rules (no AI)
   ▼
explainer.py   Claude: summary + patterns + doctor questions (level + language)
   ▼
db.py (SQLite) ► compare.py (trends, what changed)    chat_stream() (prompt caching)
```

| Claude capability | Where it's used |
|---|---|
| PDF + vision input | Reading reports and photos |
| Tool use / structured output | Extraction, verification, explanation (guaranteed JSON schema) |
| Multi-step agent pipeline | Extract → verify → human check → explain |
| Streaming | Chat tab |
| Prompt caching | Report context reused on every chat turn |
| System-prompt guardrails | No diagnosis, no medicine advice, refuses out-of-scope questions |

## 🚀 Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
python scripts/make_sample_report.py   # creates 2 fake demo reports in data/
streamlit run app.py
pytest -q                      # 10 tests for safety rules, privacy, status, compare
```

## 🎬 Demo script (2 minutes)
1. Upload `data/sample_report_march.pdf`. Show the privacy note (4 details redacted) and the verifier result.
2. Confirm → show **Connecting the dots** (iron-deficiency pattern), switch to **Hindi + Simple**, press 🔊.
3. Chat: *"Why am I tired?"* then *"Should I stop my BP tablets?"* (watch it refuse safely).
4. Upload `data/sample_report_june.pdf` → 🚨 critical potassium alert → **History** tab: Vitamin D back to normal, ferritin improved.

## ⚠️ Disclaimer
Educational project. Not medical advice. Critical thresholds are illustrative and would need clinical review before real use.
