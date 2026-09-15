"""Result & Reporting Module: the six reports listed in section 9.4 of the synopsis."""
import html
import io
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core import database as db


def user_activity_report() -> pd.DataFrame:
    return db.query_df(
        """SELECT l.log_id, u.name AS user, u.email, u.role, l.action, l.details, l.timestamp
             FROM activity_log l LEFT JOIN user u ON u.user_id = l.user_id
         ORDER BY l.log_id DESC"""
    )


def candidate_report() -> pd.DataFrame:
    return db.query_df(
        """SELECT c.candidate_id, c.name, c.email, c.phone, COUNT(r.resume_id) AS resumes,
                  GROUP_CONCAT(r.file_name, '; ') AS files, c.created_at
             FROM candidate c LEFT JOIN resume r ON r.candidate_id = c.candidate_id
         GROUP BY c.candidate_id ORDER BY c.candidate_id DESC"""
    )


def resume_analysis_report() -> pd.DataFrame:
    return db.list_resumes()[
        ["resume_id", "name", "file_name", "resume_type", "skills", "experience_years", "education",
         "ocr_confidence", "layout_score", "processing_time", "upload_date"]
    ]


def matching_result_report(job_id=None) -> pd.DataFrame:
    sql = """SELECT j.job_title, c.name, c.email, m.match_score, m.tfidf_score, m.skill_score,
                    m.experience_score, m.matched_skills, m.missing_skills, m.status, m.created_at
               FROM matching_result m
               JOIN resume r ON r.resume_id = m.resume_id
               JOIN candidate c ON c.candidate_id = r.candidate_id
               JOIN job_posting j ON j.job_id = m.job_id"""
    params: tuple = ()
    if job_id:
        sql += " WHERE m.job_id = ?"
        params = (job_id,)
    df = db.query_df(sql + " ORDER BY j.job_id, m.match_score DESC", params)
    df.insert(1, "rank", df.groupby("job_title").cumcount() + 1 if not df.empty else [])
    return df


def job_posting_report() -> pd.DataFrame:
    return db.list_jobs()


def system_performance_report() -> pd.DataFrame:
    with db.get_conn() as conn:
        q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        rows = [
            ("Total resumes processed", q("SELECT COUNT(*) FROM resume")),
            ("Text-based resumes", q("SELECT COUNT(*) FROM resume WHERE resume_type='text'")),
            ("Scanned resumes (OCR)", q("SELECT COUNT(*) FROM resume WHERE resume_type='scanned'")),
            ("Avg. parsing time - text (s)", q("SELECT ROUND(AVG(processing_time),3) FROM resume WHERE resume_type='text'")),
            ("Avg. parsing time - scanned (s)", q("SELECT ROUND(AVG(processing_time),3) FROM resume WHERE resume_type='scanned'")),
            ("Avg. OCR confidence (%)", q("SELECT ROUND(AVG(ocr_confidence),1) FROM resume WHERE ocr_confidence IS NOT NULL")),
            ("Avg. layout score", q("SELECT ROUND(AVG(layout_score),1) FROM resume")),
            ("Avg. skills per candidate", q("SELECT ROUND(AVG(n),1) FROM (SELECT COUNT(*) n FROM candidate_skill GROUP BY candidate_id)")),
            ("Job postings", q("SELECT COUNT(*) FROM job_posting")),
            ("Matches computed", q("SELECT COUNT(*) FROM matching_result")),
            ("Avg. matching time per resume (s)", q("SELECT ROUND(AVG(processing_time),4) FROM matching_result")),
            ("Avg. match score", q("SELECT ROUND(AVG(match_score),2) FROM matching_result")),
            ("Candidates selected", q("SELECT COUNT(*) FROM matching_result WHERE status='Selected'")),
            ("Selection rate (%)", q("SELECT ROUND(100.0*SUM(status='Selected')/COUNT(*),1) FROM matching_result")),
        ]
    return pd.DataFrame([(m, "—" if v is None else str(v)) for m, v in rows], columns=["metric", "value"])


REPORTS = {
    "User Activity Report": user_activity_report,
    "Candidate Report": candidate_report,
    "Resume Analysis Report": resume_analysis_report,
    "Matching Result Report": matching_result_report,
    "Job Posting Report": job_posting_report,
    "System Performance Report": system_performance_report,
}


def to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def to_pdf(title: str, df: pd.DataFrame, max_rows: int = 500, max_cell: int = 60) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1 * cm, rightMargin=1 * cm,
                            topMargin=1 * cm, bottomMargin=1 * cm, title=title)
    styles = getSampleStyleSheet()
    cell = styles["BodyText"].clone("cell", fontSize=7, leading=8.5)
    head = styles["BodyText"].clone("head", fontSize=7.5, leading=9, textColor=colors.white)

    story = [
        Paragraph(f"AI Resume Screening System — {title}", styles["Title"]),
        Paragraph(f"Generated on {datetime.now():%d %b %Y, %H:%M} · {len(df)} record(s)", styles["Normal"]),
        Spacer(1, 0.4 * cm),
    ]
    if df.empty:
        story.append(Paragraph("No records available.", styles["Normal"]))
    else:
        view = df.head(max_rows).map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
        data = [[Paragraph(html.escape(str(c)), head) for c in view.columns]]
        for row in view.itertuples(index=False):
            data.append([Paragraph(html.escape((v[:max_cell] + "…") if len(v) > max_cell else v), cell) for v in row])
        table = Table(data, repeatRows=1, colWidths=[(landscape(A4)[0] - 2 * cm) / len(view.columns)] * len(view.columns))
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e8c")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3fa")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b8c4d6")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
    doc.build(story)
    return buf.getvalue()
