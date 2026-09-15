"""Shared UI helpers."""
import streamlit as st

from core import database as db
from core import matcher

CSS = """
<style>
.block-container {padding-top: 2rem;}
.hero {text-align:center; margin: 2.5rem 0 1.5rem;}
.hero h1 {margin-bottom: 0.2rem;}
.hero p {color: #6b7280;}
.skill {display:inline-block; padding:2px 9px; margin:2px 3px 2px 0; border-radius:999px;
        font-size:0.8rem; background:rgba(59,130,246,.12); color:#1d4ed8; border:1px solid rgba(59,130,246,.25);}
.skill.miss {background:rgba(239,68,68,.10); color:#b91c1c; border-color:rgba(239,68,68,.25);}
@media (prefers-color-scheme: dark) {
  .skill {color:#93c5fd;} .skill.miss {color:#fca5a5;}
}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = ""):
    st.title(title)
    if subtitle:
        st.caption(subtitle)


def skill_chips(skills, missing=False) -> str:
    import html

    if not skills:
        return "<span style='color:#9ca3af'>—</span>"
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    cls = "skill miss" if missing else "skill"
    return "".join(f"<span class='{cls}'>{html.escape(s)}</span>" for s in skills)


def rescreen_job(job_id: int) -> int:
    """Recompute match results for one job against every stored resume."""
    job = db.get_job(job_id)
    resumes = db.resumes_for_matching()
    if not job or not resumes:
        return 0
    for res in matcher.rank_resumes(job, resumes):
        db.save_match(res["resume_id"], job_id, res)
    return len(resumes)


def rescreen_all() -> int:
    count = 0
    for job_id in db.list_jobs()["job_id"]:
        count = rescreen_job(int(job_id))
    return count
