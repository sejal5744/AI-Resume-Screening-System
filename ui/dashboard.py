import plotly.express as px
import streamlit as st

from core import database as db
from core import ocr, seed
from ui.common import page_header


def render(user):
    page_header("📊 Dashboard", "Overview of candidates, job postings and screening outcomes.")
    s = db.stats()

    c = st.columns(6)
    c[0].metric("Candidates", s["candidates"])
    c[1].metric("Scanned resumes", s["scanned"])
    c[2].metric("Job postings", s["jobs"])
    c[3].metric("Matches computed", s["matches"])
    c[4].metric("Selected", s["selected"])
    c[5].metric("Avg. match score", f"{s['avg_score']}%")

    if not ocr.ocr_available():
        st.warning("Tesseract OCR engine was not found — scanned/image resumes cannot be processed. "
                   "Install it from https://github.com/UB-Mannheim/tesseract/wiki or set `TESSERACT_CMD`.", icon="⚠️")

    if s["resumes"] == 0:
        st.info("The database is empty. Load the demo dataset (6 resumes in PDF/DOCX/TXT/image format and 3 job postings) "
                "or start by creating a job posting and uploading resumes.")
        if st.button("Load sample data", type="primary"):
            with st.spinner("Parsing sample resumes and running the matcher…"):
                summary = seed.load_samples(user["user_id"])
            st.session_state.sample_summary = summary
            st.rerun()
        return

    summary = st.session_state.pop("sample_summary", None)
    if summary:
        st.success(f"Loaded {summary['resumes']} sample resumes and {summary['jobs']} job postings.")
        for item in summary["skipped"]:
            st.caption(f"Skipped: {item}")

    resumes = db.list_resumes()
    results = db.query_df(
        """SELECT j.job_title, m.match_score, m.status FROM matching_result m
           JOIN job_posting j ON j.job_id = m.job_id"""
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Top skills in candidate pool")
        skills = resumes["skills"].dropna().str.split(", ").explode()
        if not skills.empty:
            top = skills.value_counts().head(12).rename_axis("skill").reset_index(name="candidates")
            fig = px.bar(top.sort_values("candidates"), x="candidates", y="skill", orientation="h", height=380)
            fig.update_layout(margin=dict(l=0, r=10, t=10, b=0), yaxis_title=None)
            st.plotly_chart(fig, width="stretch")
    with right:
        st.subheader("Match score distribution")
        if results.empty:
            st.caption("Run screening on a job to see scores.")
        else:
            fig = px.histogram(results, x="match_score", color="job_title", nbins=20, height=380,
                               labels={"match_score": "Match score (%)", "job_title": "Job"})
            fig.update_layout(margin=dict(l=0, r=10, t=10, b=0), bargap=0.05,
                              legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    with left:
        st.subheader("Resume formats")
        counts = resumes["resume_type"].value_counts().rename_axis("type").reset_index(name="count")
        fig = px.pie(counts, names="type", values="count", hole=0.55, height=300)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch")
    with right:
        st.subheader("Screening status by job")
        if not results.empty:
            status = results.groupby(["job_title", "status"]).size().reset_index(name="count")
            fig = px.bar(status, x="job_title", y="count", color="status", height=300,
                         color_discrete_map={"Selected": "#16a34a", "Rejected": "#dc2626", "Pending": "#9ca3af"})
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), xaxis_title=None)
            st.plotly_chart(fig, width="stretch")

    st.subheader("Recently uploaded resumes")
    st.dataframe(
        resumes.head(8)[["name", "email", "resume_type", "experience_years", "education", "layout_score", "upload_date"]],
        hide_index=True, width="stretch",
        column_config={"layout_score": st.column_config.ProgressColumn("Layout score", min_value=0, max_value=100, format="%.0f")},
    )
