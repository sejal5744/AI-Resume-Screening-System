import streamlit as st

from core import database as db
from core import nlp, parser
from core.skills import SKILLS
from ui.common import page_header, rescreen_job, skill_chips


def render(user):
    page_header("💼 Job Postings", "Create job descriptions; required skills are extracted automatically with NLP.")

    with st.expander("➕ New job posting", expanded=db.list_jobs().empty):
        jd_file = st.file_uploader("Import job description (optional)", type=["txt", "pdf", "docx"], key="jd_file")
        imported = ""
        if jd_file is not None:
            try:
                imported = nlp.clean_text(parser.extract_text(jd_file.name, jd_file.getvalue())["text"])
            except Exception as exc:
                st.error(f"Could not read file: {exc}")

        title = st.text_input("Job title", key="jd_title")
        description = st.text_area("Job description", value=imported, height=220, key=f"jd_desc_{jd_file.name if jd_file else ''}")
        detected = nlp.extract_skills(description) if description else []
        options = sorted(set(SKILLS) | set(detected))
        skills = st.multiselect("Required skills (auto-detected — edit as needed)", options, default=detected,
                                key=f"jd_skills_{hash(tuple(detected))}")
        min_exp = st.number_input("Minimum experience (years)", 0.0, 40.0,
                                  value=float(nlp.extract_experience_years(description) if description else 0), step=0.5)
        screen_now = st.checkbox("Screen all existing resumes against this job", value=True)

        if st.button("Save job posting", type="primary"):
            if not title.strip() or len(description.strip()) < 30:
                st.error("Please provide a title and a job description of at least 30 characters.")
            else:
                job_id = db.add_job(user["user_id"], title.strip(), description.strip(), skills, min_exp)
                db.log_activity(user["user_id"], "create_job", title.strip())
                n = rescreen_job(job_id) if screen_now else 0
                st.success(f"Job saved. {n} resume(s) screened." if screen_now else "Job saved.")
                st.rerun()

    jobs = db.list_jobs()
    if jobs.empty:
        st.info("No job postings yet.")
        return

    st.subheader(f"{len(jobs)} job posting(s)")
    for job in jobs.itertuples():
        with st.container(border=True):
            top = st.columns([5, 1, 1])
            top[0].markdown(f"#### {job.job_title}")
            top[0].caption(f"Posted by {job.posted_by or '—'} on {job.created_at} · min. experience {job.min_experience:g} yrs "
                           f"· {job.screened} resume(s) screened")
            if top[1].button("Re-screen", key=f"rs_{job.job_id}", width="stretch"):
                n = rescreen_job(int(job.job_id))
                db.log_activity(user["user_id"], "screen_job", f"{job.job_title}: {n} resumes")
                st.toast(f"Screened {n} resumes")
                st.rerun()
            if top[2].button("Delete", key=f"del_{job.job_id}", width="stretch"):
                db.delete_job(int(job.job_id))
                db.log_activity(user["user_id"], "delete_job", job.job_title)
                st.rerun()
            st.markdown(skill_chips(job.skills), unsafe_allow_html=True)
            with st.expander("Description"):
                st.write(job.job_description)
