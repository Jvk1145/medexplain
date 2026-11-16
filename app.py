"""MedExplain – Streamlit UI.  Run:  streamlit run app.py"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from medexplain import db
from medexplain.compare import compare
from medexplain.explainer import chat_stream, explain
from medexplain.extractor import compute_status, extract
from medexplain.llm import LLMError
from medexplain.pdf_report import build_pdf
from medexplain.prompts import LEVELS
from medexplain.red_flags import _norm_name, check
from medexplain.source import build_source
from medexplain.tts import LANG_CODES, speak
from medexplain.verifier import verify

st.set_page_config(page_title="MedExplain – Lab reports explained", page_icon=":material/vital_signs:",
                   layout="wide")

DISCLAIMER = ("MedExplain helps you understand your report. It is **not medical advice** "
              "and does not diagnose. Always consult your doctor.")
STATUS_LABEL = {"high": "High", "low": "Low", "normal": "Normal", "unknown": "—"}
STATUS_STYLE = {"High": "color: #DC2626; font-weight: 600", "Low": "color: #D97706; font-weight: 600",
                "Normal": "color: #15803D; font-weight: 600"}
EDIT_COLS = ["name", "value", "unit", "ref_low", "ref_high", "value_text", "confidence"]

ss = st.session_state
for key, default in {"report": None, "source": None, "issues": [], "confirmed": False,
                     "explanation": None, "alerts": [], "chat": [], "expl_settings": None}.items():
    ss.setdefault(key, default)


def reset():
    for key in ("report", "source", "explanation", "expl_settings"):
        ss[key] = None
    ss.issues, ss.alerts, ss.chat, ss.confirmed = [], [], [], False


def api_error(e: Exception):
    if isinstance(e, LLMError) and e.kind == "auth":
        st.error("The service is not available right now. Please try again later.",
                 icon=":material/cloud_off:")
        print("[MedExplain] AI keys invalid or missing – check .env:", e)  # shows in the terminal only
    elif isinstance(e, LLMError) and e.kind == "rate":
        st.error("The service is busy right now – please wait a minute and try again.",
                 icon=":material/hourglass_top:")
    else:
        st.error(f"Something went wrong: {e}", icon=":material/error:")


# ───────────────────────────── Sidebar ─────────────────────────────
with st.sidebar:
    st.header("MedExplain", icon=":material/vital_signs:")
    st.caption("Your lab report, explained simply.")
    st.space("small")
    existing = db.list_profiles()
    profile = st.text_input("Family member", value="Me", icon=":material/person:",
                            help=f"Saved profiles: {', '.join(existing) or 'none yet'}")
    level = st.segmented_control("Explanation level", list(LEVELS), default="Simple", required=True,
                                 width="stretch") or "Simple"
    language = st.selectbox("Language", list(LANG_CODES))
    st.space("medium")
    if st.button("Delete this profile's data", icon=":material/delete:", width="stretch"):
        db.delete_profile(profile)
        st.toast(f"Deleted all saved reports for '{profile}'.", icon=":material/check_circle:")
    st.space("small")
    st.caption(DISCLAIMER)

# ───────────────────────────── Header ─────────────────────────────
st.title("Understand your lab report", icon=":material/lab_profile:")
st.caption("Upload a blood test or lab report and get a clear, private explanation in your language – "
           "with questions to ask your doctor.")

tab_analyze, tab_chat, tab_history = st.tabs([
    ":material/description: Analyze report",
    ":material/forum: Ask about it",
    ":material/monitoring: History & trends",
])

# ───────────────────────────── Analyze ─────────────────────────────
with tab_analyze:
    if not ss.report:
        up_col, how_col = st.columns([3, 2], gap="large")
        with up_col:
            with st.container(border=True):
                st.subheader("Upload your report", icon=":material/upload_file:")
                up = st.file_uploader("Lab report (PDF or photo)", type=["pdf", "png", "jpg", "jpeg", "webp"],
                                      label_visibility="collapsed")
                st.caption(":material/lock: Names, phone numbers and IDs are removed before anything is sent.")
                analyze = st.button("Analyze report", type="primary", icon=":material/search:",
                                    disabled=up is None, width="stretch")
        with how_col:
            st.subheader("How it works", icon=":material/route:")
            for icon, title, text in (
                ("document_scanner", "1 · Read", "Every test value is extracted from your PDF or photo."),
                ("fact_check", "2 · Verify", "A second check compares each value with the original – you confirm."),
                ("psychology", "3 · Explain", "Plain-language summary, linked findings and doctor questions."),
            ):
                with st.container(border=True, horizontal=True, vertical_alignment="center"):
                    st.markdown(f":material/{icon}:", width="content")
                    st.markdown(f"**{title}**  \n:gray[{text}]")

        if up is not None and analyze:
            reset()
            try:
                with st.status("Analyzing your report…", expanded=True) as status:
                    st.write(":material/lock: Reading the file and removing personal details…")
                    src = build_source(up.getvalue(), up.name)
                    st.write(":material/table_view: Extracting every test value…")
                    report = extract(src["blocks"])
                    if not report.get("tests"):
                        raise ValueError("No lab values found. Is this a lab report?")
                    st.write(":material/fact_check: Double-checking each value against the original…")
                    issues = verify(src["blocks"], report["tests"])
                    status.update(label="Values extracted – please confirm them below", state="complete")
                ss.report, ss.source, ss.issues = report, src, issues
                st.rerun()
            except Exception as e:  # noqa: BLE001
                api_error(e)
    else:
        with st.container(horizontal=True, horizontal_alignment="right"):
            if st.button("Analyze another report", icon=":material/restart_alt:"):
                reset()
                st.rerun()

    # Step A – human confirmation of extracted values
    if ss.report and not ss.confirmed:
        src = ss.source
        st.subheader("Step 1 · Check the extracted values", icon=":material/fact_check:")
        if src["kind"] == "text":
            st.caption(f":material/lock: Privacy: only the report text was sent, with {src['redactions']} "
                       "personal detail(s) (name, phone, IDs) removed first.")
        else:
            st.caption(":material/lock: Scanned file/photo: sent as an image for reading. "
                       "Nothing is stored except test values.")

        if ss.issues:
            st.warning("\n".join(
                f"- **{i['test_name']}** ({i['problem'].replace('_', ' ')}): {i['explanation']}"
                + (f" → maybe **{i['suggested']}**" if i.get("suggested") else "") for i in ss.issues),
                title=f"{len(ss.issues)} value(s) to double-check", icon=":material/rule:")
        else:
            st.success("Every extracted value matches the original report.", icon=":material/verified:")

        df = pd.DataFrame(ss.report["tests"])
        for c in EDIT_COLS:
            if c not in df:
                df[c] = None
        edited = st.data_editor(
            df[EDIT_COLS], width="stretch", hide_index=True, disabled=["confidence"], key="editor",
            alt="Editable table of extracted lab values",
            column_config={
                "name": "Test", "value": st.column_config.NumberColumn("Value"), "unit": "Unit",
                "ref_low": st.column_config.NumberColumn("Range low"),
                "ref_high": st.column_config.NumberColumn("Range high"),
                "value_text": "As printed", "confidence": "Confidence",
            })
        st.caption("Edit any cell if something doesn't match your report.")

        if st.button("Values look right – explain my report", type="primary", icon=":material/check:"):
            for t, (_, row) in zip(ss.report["tests"], edited.iterrows()):
                for c in EDIT_COLS:
                    val = row[c]
                    t[c] = None if pd.isna(val) else (val.item() if hasattr(val, "item") else val)
                t["status"] = compute_status(t)
            ss.alerts = check(ss.report["tests"])
            try:
                with st.spinner("Connecting the dots and writing your explanation…"):
                    ss.explanation = explain(ss.report, ss.alerts, level, language)
                ss.expl_settings = (level, language)
                db.save_report(profile, ss.report)
                ss.confirmed = True
                st.rerun()
            except Exception as e:  # noqa: BLE001
                api_error(e)

    # Step B – results
    if ss.confirmed and ss.explanation:
        report, expl = ss.report, ss.explanation
        tests = report["tests"]

        for a in ss.alerts:
            st.error(a["message"], title="Urgent – please contact a doctor", icon=":material/emergency:")

        meta = " · ".join(x for x in (report.get("lab_name"), report.get("report_date")) if x)
        if meta:
            st.caption(f":material/event: {meta}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Tests found", len(tests), border=True, icon=":material/biotech:")
        m2.metric("Normal", sum(t["status"] == "normal" for t in tests), border=True,
                  icon=":material/check_circle:")
        m3.metric("Out of range", sum(t["status"] in ("high", "low") for t in tests), border=True,
                  icon=":material/warning:")

        if ss.expl_settings != (level, language):
            if st.button(f"Re-explain in {language} ({level})", icon=":material/translate:"):
                try:
                    with st.spinner("Rewriting…"):
                        ss.explanation = explain(report, ss.alerts, level, language)
                        ss.expl_settings = (level, language)
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    api_error(e)

        with st.container(border=True):
            st.subheader("Summary", icon=":material/summarize:")
            st.markdown(expl["overall_summary"])
            with st.container(horizontal=True):
                listen = st.button("Listen", icon=":material/volume_up:")
                try:
                    st.download_button(
                        "Download PDF summary", build_pdf(report, expl, ss.alerts, profile), type="primary",
                        icon=":material/download:", mime="application/pdf",
                        file_name=f"medexplain_summary_{report.get('report_date') or 'report'}.pdf")
                except Exception as e:  # noqa: BLE001
                    st.error(f"Could not create the PDF: {e}")
            if listen:
                audio = speak(expl["overall_summary"], language)
                if audio:
                    st.audio(audio, format="audio/mp3")
                else:
                    st.warning("Voice needs an internet connection.", icon=":material/wifi_off:")

        st.subheader("Your results", icon=":material/table_chart:")
        table = pd.DataFrame([{
            "Test": t["name"], "Result": str(t.get("value_text") or t.get("value") or ""),
            "Unit": t.get("unit", ""),
            "Normal range": t.get("ref_text") or f"{t.get('ref_low')} – {t.get('ref_high')}",
            "Status": STATUS_LABEL[t["status"]]} for t in tests])
        st.dataframe(table.style.map(lambda v: STATUS_STYLE.get(v, ""), subset=["Status"]),
                     width="stretch", hide_index=True, alt="Lab results with status")

        if expl["patterns"]:
            st.subheader("Connecting the dots", icon=":material/hub:")
            st.caption("Doctors read reports as patterns, not single numbers.")
            cols = st.columns(2)
            for i, p in enumerate(expl["patterns"]):
                with cols[i % 2].container(border=True, height="stretch"):
                    st.markdown(" ".join(f":blue-badge[{n}]" for n in p["tests_involved"]))
                    st.markdown(p["observation"])
                    st.caption(p["why_it_matters"])

        if expl["test_explanations"]:
            st.subheader("Out-of-range values explained", icon=":material/search_insights:")
            for e in expl["test_explanations"]:
                with st.expander(e["test_name"], icon=":material/info:"):
                    st.markdown(f"**What it is:** {e['what_it_is']}")
                    st.markdown(f"**Your result:** {e['what_your_result_means']}")

        col_q, col_t = st.columns(2)
        with col_q.container(border=True, height="stretch"):
            st.subheader("Ask your doctor", icon=":material/stethoscope:")
            st.markdown("\n".join(f"- {q}" for q in expl["doctor_questions"]))
        with col_t.container(border=True, height="stretch"):
            st.subheader("Healthy habits", icon=":material/nutrition:")
            st.markdown("\n".join(f"- {tip}" for tip in expl["lifestyle_tips"]))

        st.caption(f":material/info: {DISCLAIMER}")

# ───────────────────────────── Chat ─────────────────────────────
with tab_chat:
    if not ss.confirmed:
        st.info("Analyze a report first, then ask anything about it here.", icon=":material/forum:")
    else:
        st.caption('Try: "Why is my hemoglobin low?" · "What foods help?" · "Is anything serious?"')
        for m in ss.chat:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
        if q := st.chat_input("Ask about your report…"):
            ss.chat.append({"role": "user", "content": q})
            with st.chat_message("user"):
                st.markdown(q)
            with st.chat_message("assistant"):
                try:
                    answer = st.write_stream(chat_stream(ss.report, ss.chat, language))
                    ss.chat.append({"role": "assistant", "content": answer})
                except Exception as e:  # noqa: BLE001
                    ss.chat.pop()
                    api_error(e)

# ───────────────────────────── History ─────────────────────────────
with tab_history:
    reports = db.list_reports(profile)
    if not reports:
        st.info(f"No saved reports for '{profile}' yet. Analyze one to start tracking.",
                icon=":material/monitoring:")
    else:
        st.subheader(f"Trends for {profile}", icon=":material/show_chart:")
        names = {}
        for r in reports:
            for t in r["data"]["tests"]:
                if t.get("value") is not None:
                    names.setdefault(_norm_name(t["name"]), t["name"])
        choice = st.selectbox("Test", sorted(names.values())) if names else None
        key = _norm_name(choice) if choice else None
        pts = [(r["report_date"], t) for r in reports for t in r["data"]["tests"]
               if key and _norm_name(t["name"]) == key and t.get("value") is not None]
        if pts:
            fig = go.Figure()
            dates = [d for d, _ in pts]
            lo, hi = pts[-1][1].get("ref_low"), pts[-1][1].get("ref_high")
            if lo is not None and hi is not None:
                fig.add_hrect(y0=lo, y1=hi, fillcolor="#15803D", opacity=0.10, line_width=0,
                              annotation_text="normal range", annotation_position="top left")
            fig.add_trace(go.Scatter(x=dates, y=[t["value"] for _, t in pts], mode="lines+markers",
                                     name=choice, line=dict(width=3), marker=dict(size=9)))
            fig.update_layout(yaxis_title=pts[-1][1].get("unit", ""), height=360,
                              margin=dict(l=10, r=10, t=30, b=10))
            with st.container(border=True):
                st.plotly_chart(fig, width="stretch")

        if len(reports) >= 2:
            st.subheader("What changed?", icon=":material/compare_arrows:")
            labels = [f"{r['report_date']} · {r['lab_name'] or 'report'} (#{r['id']})" for r in reports]
            a, b = st.columns(2)
            i_old = a.selectbox("Older report", range(len(reports)), format_func=lambda i: labels[i], index=0)
            i_new = b.selectbox("Newer report", range(len(reports)), format_func=lambda i: labels[i],
                                index=len(reports) - 1)
            diff = compare(reports[i_old]["data"], reports[i_new]["data"])
            groups = [("Back to normal", "back_to_normal", "check_circle", "green"),
                      ("Improved", "improved", "trending_up", "blue"),
                      ("Newly out of range", "newly_abnormal", "warning", "orange"),
                      ("Got worse", "worsened", "trending_down", "red")]
            cols = st.columns(4)
            for col, (title, k, icon, colour) in zip(cols, groups):
                with col.container(border=True, height="stretch"):
                    st.markdown(f":{colour}[:material/{icon}: **{title}**] · {len(diff[k])}")
                    for row in diff[k]:
                        st.caption(f"{row['test']}: {row['old']} → {row['new']} {row['unit']}")
