"""SQLite storage for report history (per family-member profile)."""
import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.getenv("MEDEXPLAIN_DB", os.path.join(os.path.dirname(__file__), "..", "data", "medexplain.db"))


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile TEXT NOT NULL,
        report_date TEXT,
        lab_name TEXT,
        created_at TEXT NOT NULL,
        data TEXT NOT NULL)""")
    return c


def save_report(profile: str, report: dict) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO reports (profile, report_date, lab_name, created_at, data) VALUES (?,?,?,?,?)",
            (profile, report.get("report_date") or "", report.get("lab_name") or "",
             datetime.now().isoformat(timespec="seconds"), json.dumps(report, ensure_ascii=False)))
        return cur.lastrowid


def list_profiles() -> list[str]:
    with _conn() as c:
        return [r[0] for r in c.execute("SELECT DISTINCT profile FROM reports ORDER BY profile")]


def list_reports(profile: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, report_date, lab_name, created_at, data FROM reports WHERE profile=? "
            "ORDER BY COALESCE(NULLIF(report_date,''), created_at)", (profile,)).fetchall()
    return [{"id": r[0], "report_date": r[1] or r[3][:10], "lab_name": r[2], "data": json.loads(r[4])}
            for r in rows]


def delete_profile(profile: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM reports WHERE profile=?", (profile,))
