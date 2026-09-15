"""Database module (SQLite).

Implements the schema from the synopsis (section 8 / ER diagram):
USER, CANDIDATE, SKILL, CANDIDATE_SKILL, RESUME, JOB_POSTING, JOB_SKILL,
MATCHING_RESULT, plus ACTIVITY_LOG for the User Activity / System Performance reports.
All queries are parameterised to prevent SQL injection.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import pandas as pd

import config

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS user (
    user_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    password    TEXT NOT NULL,              -- bcrypt hash, never plain text
    role        TEXT NOT NULL DEFAULT 'recruiter',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate (
    candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT,
    email        TEXT,
    phone        TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill (
    skill_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS candidate_skill (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidate(candidate_id) ON DELETE CASCADE,
    skill_id     INTEGER NOT NULL REFERENCES skill(skill_id) ON DELETE CASCADE,
    UNIQUE(candidate_id, skill_id)
);

CREATE TABLE IF NOT EXISTS resume (
    resume_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id     INTEGER NOT NULL REFERENCES candidate(candidate_id) ON DELETE CASCADE,
    file_name        TEXT NOT NULL,
    resume_text      TEXT,
    processed_text   TEXT,
    resume_type      TEXT NOT NULL,          -- 'text' or 'scanned'
    upload_date      TEXT NOT NULL,
    ocr_confidence   REAL,
    layout_score     REAL,
    experience_years REAL,
    education        TEXT,
    processing_time  REAL,
    uploaded_by      INTEGER REFERENCES user(user_id)
);

CREATE TABLE IF NOT EXISTS job_posting (
    job_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER REFERENCES user(user_id),
    job_title       TEXT NOT NULL,
    job_description TEXT NOT NULL,
    min_experience  REAL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_skill (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id   INTEGER NOT NULL REFERENCES job_posting(job_id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skill(skill_id) ON DELETE CASCADE,
    UNIQUE(job_id, skill_id)
);

CREATE TABLE IF NOT EXISTS matching_result (
    match_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id        INTEGER NOT NULL REFERENCES resume(resume_id) ON DELETE CASCADE,
    job_id           INTEGER NOT NULL REFERENCES job_posting(job_id) ON DELETE CASCADE,
    match_score      REAL NOT NULL,
    tfidf_score      REAL,
    skill_score      REAL,
    experience_score REAL,
    matched_skills   TEXT,
    missing_skills   TEXT,
    status           TEXT NOT NULL DEFAULT 'Pending',   -- Pending / Selected / Rejected
    processing_time  REAL,
    created_at       TEXT NOT NULL,
    UNIQUE(resume_id, job_id)
);

CREATE TABLE IF NOT EXISTS activity_log (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES user(user_id) ON DELETE SET NULL,
    action     TEXT NOT NULL,
    details    TEXT,
    timestamp  TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def get_conn(db_path=None):
    conn = sqlite3.connect(str(db_path or config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)


# ---------------------------------------------------------------- users
def create_user(name, email, password_hash, role="recruiter"):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO user (name, email, password, role, created_at) VALUES (?,?,?,?,?)",
            (name, email.lower().strip(), password_hash, role, now()),
        )
        return cur.lastrowid


def get_user_by_email(email):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM user WHERE email = ?", (email.lower().strip(),)).fetchone()
        return dict(row) if row else None


def update_password(user_id, password_hash):
    with get_conn() as conn:
        conn.execute("UPDATE user SET password = ? WHERE user_id = ?", (password_hash, user_id))


def count_users():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM user").fetchone()[0]


def log_activity(user_id, action, details=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO activity_log (user_id, action, details, timestamp) VALUES (?,?,?,?)",
            (user_id, action, details, now()),
        )


# ---------------------------------------------------------------- skills
def _skill_ids(conn, skills):
    ids = []
    for s in sorted(set(skills)):
        conn.execute("INSERT OR IGNORE INTO skill (skill_name) VALUES (?)", (s,))
        ids.append(conn.execute("SELECT skill_id FROM skill WHERE skill_name = ?", (s,)).fetchone()[0])
    return ids


# ---------------------------------------------------------------- candidates / resumes
def add_candidate_with_resume(info: dict, user_id=None) -> int:
    """Insert candidate, resume and candidate skills in one transaction. Returns resume_id."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO candidate (name, email, phone, created_at) VALUES (?,?,?,?)",
            (info.get("name"), info.get("email"), info.get("phone"), now()),
        )
        candidate_id = cur.lastrowid
        for sid in _skill_ids(conn, info.get("skills", [])):
            conn.execute(
                "INSERT OR IGNORE INTO candidate_skill (candidate_id, skill_id) VALUES (?,?)",
                (candidate_id, sid),
            )
        cur = conn.execute(
            """INSERT INTO resume (candidate_id, file_name, resume_text, processed_text, resume_type,
                   upload_date, ocr_confidence, layout_score, experience_years, education,
                   processing_time, uploaded_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                candidate_id, info["file_name"], info["resume_text"], info["processed_text"],
                info["resume_type"], now(), info.get("ocr_confidence"), info.get("layout_score"),
                info.get("experience_years"), info.get("education"), info.get("processing_time"), user_id,
            ),
        )
        return cur.lastrowid


def list_resumes() -> pd.DataFrame:
    return query_df(
        """SELECT r.resume_id, c.candidate_id, c.name, c.email, c.phone, r.file_name, r.resume_type,
                  r.experience_years, r.education, r.ocr_confidence, r.layout_score,
                  r.upload_date, r.processing_time,
                  (SELECT GROUP_CONCAT(s.skill_name, ', ') FROM candidate_skill cs
                     JOIN skill s ON s.skill_id = cs.skill_id
                    WHERE cs.candidate_id = c.candidate_id) AS skills
             FROM resume r JOIN candidate c ON c.candidate_id = r.candidate_id
         ORDER BY r.resume_id DESC"""
    )


def get_resume(resume_id):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT r.*, c.name, c.email, c.phone FROM resume r
               JOIN candidate c ON c.candidate_id = r.candidate_id WHERE r.resume_id = ?""",
            (resume_id,),
        ).fetchone()
        return dict(row) if row else None


def resumes_for_matching():
    """Resume rows plus their skill list, ready for the matcher."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT r.resume_id, r.candidate_id, r.processed_text, r.experience_years, c.name
                 FROM resume r JOIN candidate c ON c.candidate_id = r.candidate_id"""
        ).fetchall()
        out = []
        for r in rows:
            skills = [
                s[0] for s in conn.execute(
                    """SELECT s.skill_name FROM candidate_skill cs JOIN skill s ON s.skill_id = cs.skill_id
                       WHERE cs.candidate_id = ?""",
                    (r["candidate_id"],),
                )
            ]
            out.append({**dict(r), "skills": skills})
        return out


def delete_candidate(candidate_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM candidate WHERE candidate_id = ?", (candidate_id,))


# ---------------------------------------------------------------- jobs
def add_job(user_id, title, description, skills, min_experience=0.0) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO job_posting (user_id, job_title, job_description, min_experience, created_at)
               VALUES (?,?,?,?,?)""",
            (user_id, title, description, min_experience, now()),
        )
        job_id = cur.lastrowid
        for sid in _skill_ids(conn, skills):
            conn.execute("INSERT OR IGNORE INTO job_skill (job_id, skill_id) VALUES (?,?)", (job_id, sid))
        return job_id


def list_jobs() -> pd.DataFrame:
    return query_df(
        """SELECT j.job_id, j.job_title, j.job_description, j.min_experience, j.created_at,
                  u.name AS posted_by,
                  (SELECT GROUP_CONCAT(s.skill_name, ', ') FROM job_skill js
                     JOIN skill s ON s.skill_id = js.skill_id WHERE js.job_id = j.job_id) AS skills,
                  (SELECT COUNT(*) FROM matching_result m WHERE m.job_id = j.job_id) AS screened
             FROM job_posting j LEFT JOIN user u ON u.user_id = j.user_id
         ORDER BY j.job_id DESC"""
    )


def get_job(job_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM job_posting WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        skills = [
            s[0] for s in conn.execute(
                "SELECT s.skill_name FROM job_skill js JOIN skill s ON s.skill_id = js.skill_id WHERE js.job_id = ?",
                (job_id,),
            )
        ]
        return {**dict(row), "skills": skills}


def delete_job(job_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM job_posting WHERE job_id = ?", (job_id,))


# ---------------------------------------------------------------- matching results
def save_match(resume_id, job_id, res: dict):
    """Upsert a match result, preserving a recruiter's manual status decision."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO matching_result (resume_id, job_id, match_score, tfidf_score, skill_score,
                   experience_score, matched_skills, missing_skills, status, processing_time, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(resume_id, job_id) DO UPDATE SET
                   match_score=excluded.match_score, tfidf_score=excluded.tfidf_score,
                   skill_score=excluded.skill_score, experience_score=excluded.experience_score,
                   matched_skills=excluded.matched_skills, missing_skills=excluded.missing_skills,
                   processing_time=excluded.processing_time, created_at=excluded.created_at""",
            (
                resume_id, job_id, res["match_score"], res["tfidf_score"], res["skill_score"],
                res["experience_score"], ", ".join(res["matched_skills"]), ", ".join(res["missing_skills"]),
                "Pending", res.get("processing_time"), now(),
            ),
        )


def results_for_job(job_id) -> pd.DataFrame:
    df = query_df(
        """SELECT m.match_id, m.resume_id, c.name, c.email, c.phone, r.file_name, r.resume_type,
                  r.experience_years, m.match_score, m.tfidf_score, m.skill_score, m.experience_score,
                  m.matched_skills, m.missing_skills, m.status, m.created_at
             FROM matching_result m
             JOIN resume r ON r.resume_id = m.resume_id
             JOIN candidate c ON c.candidate_id = r.candidate_id
            WHERE m.job_id = ?
         ORDER BY m.match_score DESC""",
        (job_id,),
    )
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


def set_status(match_id, status):
    if status not in {"Pending", "Selected", "Rejected"}:
        raise ValueError("Invalid status")
    with get_conn() as conn:
        conn.execute("UPDATE matching_result SET status = ? WHERE match_id = ?", (status, match_id))


def auto_shortlist(job_id, threshold):
    with get_conn() as conn:
        conn.execute(
            """UPDATE matching_result SET status = CASE WHEN match_score >= ? THEN 'Selected' ELSE 'Rejected' END
               WHERE job_id = ?""",
            (threshold, job_id),
        )


def stats() -> dict:
    with get_conn() as conn:
        one = lambda q: conn.execute(q).fetchone()[0]  # noqa: E731
        return {
            "candidates": one("SELECT COUNT(*) FROM candidate"),
            "resumes": one("SELECT COUNT(*) FROM resume"),
            "scanned": one("SELECT COUNT(*) FROM resume WHERE resume_type = 'scanned'"),
            "jobs": one("SELECT COUNT(*) FROM job_posting"),
            "matches": one("SELECT COUNT(*) FROM matching_result"),
            "selected": one("SELECT COUNT(*) FROM matching_result WHERE status = 'Selected'"),
            "avg_score": one("SELECT ROUND(AVG(match_score), 1) FROM matching_result") or 0,
        }
