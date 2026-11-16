"""Generate FAKE sample lab reports for demos (fictional patient, fictional lab).

python scripts/make_sample_report.py
-> data/sample_report_march.pdf  (iron-deficiency pattern, low vitamin D, high LDL)
-> data/sample_report_june.pdf   (improved follow-up + one critical potassium for the red-flag demo)
"""
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = os.path.join(os.path.dirname(__file__), "..", "data")

MARCH = [
    ("COMPLETE BLOOD COUNT", None),
    ("Hemoglobin (Hb)", "9.8", "g/dL", "12.0 - 15.5", "L"),
    ("RBC Count", "4.1", "million/cumm", "4.2 - 5.4", "L"),
    ("MCV", "72", "fL", "80 - 100", "L"),
    ("MCH", "23.5", "pg", "27 - 32", "L"),
    ("Total Leukocyte Count", "7800", "/cumm", "4000 - 11000", ""),
    ("Platelet Count", "2.6", "lakh/cumm", "1.5 - 4.5", ""),
    ("IRON STUDIES", None),
    ("Serum Ferritin", "8", "ng/mL", "15 - 150", "L"),
    ("LIPID PROFILE", None),
    ("Total Cholesterol", "228", "mg/dL", "< 200", "H"),
    ("LDL Cholesterol", "152", "mg/dL", "< 100", "H"),
    ("HDL Cholesterol", "41", "mg/dL", "> 50", "L"),
    ("Triglycerides", "160", "mg/dL", "< 150", "H"),
    ("OTHERS", None),
    ("Glucose Fasting", "92", "mg/dL", "70 - 100", ""),
    ("HbA1c", "5.4", "%", "4.0 - 5.6", ""),
    ("TSH", "2.1", "uIU/mL", "0.4 - 4.0", ""),
    ("Vitamin D (25-OH)", "14", "ng/mL", "30 - 100", "L"),
    ("Serum Potassium", "4.3", "mmol/L", "3.5 - 5.1", ""),
]

JUNE = [
    ("COMPLETE BLOOD COUNT", None),
    ("Hemoglobin (Hb)", "11.9", "g/dL", "12.0 - 15.5", "L"),
    ("RBC Count", "4.3", "million/cumm", "4.2 - 5.4", ""),
    ("MCV", "79", "fL", "80 - 100", "L"),
    ("MCH", "26.4", "pg", "27 - 32", "L"),
    ("Total Leukocyte Count", "7200", "/cumm", "4000 - 11000", ""),
    ("Platelet Count", "2.8", "lakh/cumm", "1.5 - 4.5", ""),
    ("IRON STUDIES", None),
    ("Serum Ferritin", "24", "ng/mL", "15 - 150", ""),
    ("LIPID PROFILE", None),
    ("Total Cholesterol", "205", "mg/dL", "< 200", "H"),
    ("LDL Cholesterol", "131", "mg/dL", "< 100", "H"),
    ("HDL Cholesterol", "46", "mg/dL", "> 50", "L"),
    ("Triglycerides", "142", "mg/dL", "< 150", ""),
    ("OTHERS", None),
    ("Glucose Fasting", "95", "mg/dL", "70 - 100", ""),
    ("HbA1c", "5.5", "%", "4.0 - 5.6", ""),
    ("TSH", "2.4", "uIU/mL", "0.4 - 4.0", ""),
    ("Vitamin D (25-OH)", "31", "ng/mL", "30 - 100", ""),
    ("Serum Potassium", "6.6", "mmol/L", "3.5 - 5.1", "H"),
]


def build(path, rows, date, lab_no):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=36, bottomMargin=36)
    story = [
        Paragraph("<b>SAMPLE DIAGNOSTICS LAB (FICTIONAL)</b>", styles["Title"]),
        Paragraph("Demo report generated for testing MedExplain – not a real patient.", styles["Italic"]),
        Spacer(1, 10),
        Paragraph("Patient Name : Test Patient", styles["Normal"]),
        Paragraph("Age : 34 Years &nbsp;&nbsp; Sex : Female", styles["Normal"]),
        Paragraph("Mobile : 9876500000", styles["Normal"]),
        Paragraph(f"Lab No : {lab_no}", styles["Normal"]),
        Paragraph(f"Report Date : {date}", styles["Normal"]),
        Paragraph("Ref. By : Dr. Example", styles["Normal"]),
        Spacer(1, 12),
    ]
    data = [["Test", "Result", "Unit", "Reference Range", "Flag"]]
    section_rows = []
    for r in rows:
        if r[1] is None:
            section_rows.append(len(data))
            data.append([r[0], "", "", "", ""])
        else:
            data.append(list(r))
    tbl = Table(data, colWidths=[170, 60, 85, 110, 40])
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
             ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
             ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
             ("FONTSIZE", (0, 0), (-1, -1), 9)]
    for i in section_rows:
        style += [("SPAN", (0, i), (-1, i)), ("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"),
                  ("BACKGROUND", (0, i), (-1, i), colors.whitesmoke)]
    tbl.setStyle(TableStyle(style))
    story += [tbl, Spacer(1, 14), Paragraph("*** End of report ***", styles["Normal"])]
    doc.build(story)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    build(os.path.join(OUT, "sample_report_march.pdf"), MARCH, "2026-03-10", "LB-1001")
    build(os.path.join(OUT, "sample_report_june.pdf"), JUNE, "2026-06-12", "LB-2044")
    print("Created sample reports in", os.path.abspath(OUT))
