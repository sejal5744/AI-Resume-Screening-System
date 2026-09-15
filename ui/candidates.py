import streamlit as st

from core import database as db
from core import matcher
from ui.common import page_header, skill_chips


def render(user):
    page_header("👥 Candidates", "Browse parsed candidate profiles and see which jobs suit them best.")
    resumes = db.list_resumes()
    if resumes.empty:
        st.info("No candidates yet. Upload resumes first.")
        return

    query = st.text_input("Search by name, email or skill", placeholder="e.g. python, opencv, priya")
    view = resumes
    if query.strip():
        q = query.strip().lower()
        mask = resumes[["name", "email", "skills", "file_name"]].fillna("").apply(
            lambda col: col.str.lower().str.contains(q, regex=False)).any(axis=1)
        view = resumes[mask]

    st.dataframe(
        view[["resume_id", "name", "email", "phone", "resume_type", "experience_years", "education",
              "layout_score", "ocr_confidence", "skills"]],
        hide_index=True, width="stretch",
        column_config={
            "resume_id": st.column_config.NumberColumn("ID", format="%d"),
            "layout_score": st.column_config.ProgressColumn("Layout", min_value=0, max_value=100, format="%.0f"),
            "ocr_confidence": st.column_config.NumberColumn("OCR conf. %", format="%.0f"),
        },
    )
    if view.empty:
        return

    labels = {int(r.resume_id): f"{r.name} — {r.file_name}" for r in view.itertuples()}
    resume_id = st.selectbox("Candidate details", list(labels), format_func=labels.get)
    r = db.get_resume(resume_id)
    row = resumes[resumes["resume_id"] == resume_id].iloc[0]

    with st.container(border=True):
        a, b = st.columns([3, 1])
        a.markdown(f"### {r['name']}\n{r['email'] or '—'} · {r['phone'] or '—'}")
        a.caption(f"{r['file_name']} · uploaded {r['upload_date']} · {r['resume_type']} · parsed in {r['processing_time'] or 0:.2f}s")
        if b.button("Delete candidate", type="secondary", width="stretch"):
            db.delete_candidate(int(r["candidate_id"]))
            db.log_activity(user["user_id"], "delete_candidate", r["name"] or "")
            st.rerun()

        m = st.columns(4)
        m[0].metric("Experience", f"{(r['experience_years'] or 0):g} yrs")
        m[1].metric("Education", r["education"] or "—")
        m[2].metric("Layout score", f"{(r['layout_score'] or 0):.0f}")
        m[3].metric("OCR confidence", f"{r['ocr_confidence']:.0f}%" if r["ocr_confidence"] is not None else "n/a")
        st.markdown(skill_chips(row["skills"]), unsafe_allow_html=True)

        st.markdown("#### Recommended job roles")
        jobs = db.list_jobs()
        if jobs.empty:
            st.caption("No job postings to compare against.")
        else:
            candidate = [x for x in db.resumes_for_matching() if x["resume_id"] == resume_id]
            recs = []
            for j in jobs.itertuples():
                job = db.get_job(int(j.job_id))
                res = matcher.rank_resumes(job, candidate)[0]
                recs.append({"job": j.job_title, "match_score": res["match_score"],
                             "missing_skills": ", ".join(res["missing_skills"]) or "—"})
            recs.sort(key=lambda x: x["match_score"], reverse=True)
            st.dataframe(recs, hide_index=True, width="stretch", column_config={
                "match_score": st.column_config.ProgressColumn("Match %", min_value=0, max_value=100, format="%.1f")})

        with st.expander("Extracted resume text"):
            st.text(r["resume_text"] or "")
