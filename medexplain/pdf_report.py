"""Build a clean, printable PDF summary of an explained report (for the patient / doctor).

Uses fpdf2 with text shaping so Hindi, Telugu, Tamil, etc. render correctly
(needs a Unicode font – Nirmala UI on Windows, or Noto/DejaVu fonts elsewhere).
"""
import logging
import os
import re
from datetime import date

from fpdf import FPDF
from fpdf.fonts import FontFace

logging.getLogger("fontTools").setLevel(logging.ERROR)  # hide harmless font-subsetting notices

# (regular, bold) font candidates – first pair that exists is used.
FONT_CANDIDATES = [
    (os.path.join(os.path.dirname(__file__), "fonts", "NotoSans-Regular.ttf"),
     os.path.join(os.path.dirname(__file__), "fonts", "NotoSans-Bold.ttf")),
    (r"C:\Windows\Fonts\Nirmala.ttf", r"C:\Windows\Fonts\NirmalaB.ttf"),  # all Indian scripts
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
]

BLUE = (25, 90, 160)
GREY = (110, 110, 110)
STATUS = {  # label, text colour
    "high": ("High", (190, 30, 45)),
    "low": ("Low", (200, 110, 0)),
    "normal": ("Normal", (30, 130, 60)),
    "unknown": ("-", GREY),
}
_EMOJI = re.compile("[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE0F\u200d]")
_latin_only = False  # True when no Unicode font is available (Helvetica fallback)


def _clean(text) -> str:
    """Strip emojis (PDF fonts don't have them) and normalise None / numbers."""
    if text is None:
        return ""
    if isinstance(text, float):
        text = f"{text:g}"
    text = _EMOJI.sub("", str(text)).strip()
    return text.encode("latin-1", "replace").decode("latin-1") if _latin_only else text


class _PDF(FPDF):
    font_name = "Helvetica"

    def footer(self):
        self.set_y(-12)
        self.set_font(self.font_name, size=8)
        self.set_text_color(*GREY)
        self.cell(0, 6, f"Not medical advice - always consult your doctor.  |  MedExplain  |  "
                        f"Page {self.page_no()}/{{nb}}", align="C")


def _setup_font(pdf: _PDF):
    global _latin_only
    _latin_only = False
    for regular, bold in FONT_CANDIDATES:
        if os.path.exists(regular) and os.path.exists(bold):
            pdf.add_font("Body", "", regular)
            pdf.add_font("Body", "B", bold)
            pdf.font_name = "Body"
            try:
                pdf.set_text_shaping(True)  # correct joining for Indian scripts
            except Exception:  # noqa: BLE001 – uharfbuzz not installed
                pass
            return
    _latin_only = True  # no Unicode font found: Helvetica only supports Latin-1 text


def _heading(pdf: _PDF, text: str):
    pdf.ln(3)
    pdf.set_font(pdf.font_name, "B", 13)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*BLUE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)
    pdf.set_font(pdf.font_name, size=10.5)
    pdf.set_text_color(0, 0, 0)


def _para(pdf: _PDF, text: str, bold_prefix: str = ""):
    pdf.set_font(pdf.font_name, size=10.5)
    pdf.set_text_color(0, 0, 0)
    if bold_prefix:
        pdf.multi_cell(0, 6, f"**{_clean(bold_prefix)}** {_clean(text)}", markdown=True, align="L",
                       new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.multi_cell(0, 6, _clean(text), new_x="LMARGIN", new_y="NEXT")


def _bullets(pdf: _PDF, items):
    for item in items:
        pdf.set_x(pdf.l_margin + 3)
        pdf.multi_cell(0, 6, "-  " + _clean(item), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(0.5)


def build_pdf(report: dict, expl: dict, alerts: list, profile: str = "") -> bytes:
    pdf = _PDF(format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(True, margin=18)
    _setup_font(pdf)
    pdf.add_page()

    # ── Title block ──
    pdf.set_font(pdf.font_name, "B", 20)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 11, "MedExplain - Lab Report Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(pdf.font_name, size=10)
    pdf.set_text_color(*GREY)
    meta = [f"Lab: {_clean(report.get('lab_name')) or '-'}",
            f"Report date: {_clean(report.get('report_date')) or '-'}"]
    if profile:
        meta.insert(0, f"For: {_clean(profile)}")
    meta.append(f"Generated: {date.today():%d %b %Y}")
    pdf.cell(0, 6, "   |   ".join(meta), new_x="LMARGIN", new_y="NEXT")

    tests = report.get("tests", [])
    n_abn = sum(t.get("status") in ("high", "low") for t in tests)
    n_norm = sum(t.get("status") == "normal" for t in tests)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 7, f"{len(tests)} tests   |   {n_norm} normal   |   {n_abn} out of range",
             new_x="LMARGIN", new_y="NEXT")

    # ── Urgent alerts ──
    if alerts:
        pdf.ln(3)
        pdf.set_fill_color(253, 230, 230)
        pdf.set_draw_color(190, 30, 45)
        pdf.set_text_color(150, 20, 30)
        pdf.set_font(pdf.font_name, "B", 11)
        text = "URGENT - please contact a doctor:\n" + "\n".join("- " + _clean(a["message"]) for a in alerts)
        pdf.multi_cell(0, 6.5, text, border=1, fill=True, padding=3, new_x="LMARGIN", new_y="NEXT")

    # ── Summary ──
    _heading(pdf, "Summary")
    _para(pdf, expl.get("overall_summary", ""))

    # ── Results table ──
    _heading(pdf, "Your results")
    pdf.set_font(pdf.font_name, size=9.5)
    pdf.set_draw_color(200, 200, 200)
    head = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=BLUE)
    with pdf.table(col_widths=(36, 16, 14, 22, 12), line_height=6, headings_style=head,
                   text_align=("LEFT", "LEFT", "LEFT", "LEFT", "CENTER"),
                   cell_fill_color=(244, 247, 251), cell_fill_mode="ROWS") as table:
        row = table.row()
        for h in ("Test", "Result", "Unit", "Normal range", "Status"):
            row.cell(h)
        for t in tests:
            label, colour = STATUS.get(t.get("status"), STATUS["unknown"])
            ref = t.get("ref_text") or (f"{_clean(t.get('ref_low'))} - {_clean(t.get('ref_high'))}"
                                        if t.get("ref_low") is not None or t.get("ref_high") is not None else "")
            row = table.row()
            row.cell(_clean(t.get("name")))
            row.cell(_clean(t.get("value_text") or t.get("value")))
            row.cell(_clean(t.get("unit")))
            row.cell(_clean(ref))
            row.cell(label, style=FontFace(emphasis="BOLD", color=colour))

    # ── Patterns ──
    if expl.get("patterns"):
        _heading(pdf, "Connecting the dots")
        for p in expl["patterns"]:
            _para(pdf, p.get("observation", ""), bold_prefix=" + ".join(p.get("tests_involved", [])) + ":")
            if p.get("why_it_matters"):
                pdf.set_text_color(*GREY)
                pdf.set_font(pdf.font_name, size=9.5)
                pdf.multi_cell(0, 5.5, _clean(p["why_it_matters"]), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

    # ── Out-of-range explanations ──
    if expl.get("test_explanations"):
        _heading(pdf, "Out-of-range values explained")
        for e in expl["test_explanations"]:
            pdf.set_font(pdf.font_name, "B", 11)
            pdf.cell(0, 7, _clean(e.get("test_name")), new_x="LMARGIN", new_y="NEXT")
            _para(pdf, e.get("what_it_is", ""), bold_prefix="What it is:")
            _para(pdf, e.get("what_your_result_means", ""), bold_prefix="Your result:")
            pdf.ln(2)

    # ── Doctor questions & habits ──
    if expl.get("doctor_questions"):
        _heading(pdf, "Questions to ask your doctor")
        _bullets(pdf, expl["doctor_questions"])
    if expl.get("lifestyle_tips"):
        _heading(pdf, "Healthy habits")
        _bullets(pdf, expl["lifestyle_tips"])

    pdf.ln(4)
    pdf.set_font(pdf.font_name, size=9)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(0, 5, "MedExplain helps you understand your report. It is not medical advice and does "
                         "not diagnose. Always consult your doctor.", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
