import plotly.express as px
import streamlit as st

import config
from core import database as db
from core import reports
from ui.common import page_header, rescreen_job, skill_chips


def render(user):
    page_header("🏆 Screening & Ranking",
                "Candidates ranked by TF-IDF content similarity, required-skill coverage and experience fit.")
    jobs = db.list_jobs()
    if jobs.empty:
        st.info("Create a job posting first.")
        return

    job_labels = {int(r.job_id): r.job_title for r in jobs.itertuples()}
    job_id = st.selectbox("Job posting", list(job_labels), format_func=job_labels.get)
    job = db.get_job(job_id)

    c1, c2 = st.columns([3, 1])
    c1.markdown("**Required skills:** " + skill_chips(job["skills"]), unsafe_allow_html=True)
    if c2.button("🔄 Run screening", type="primary", width="stretch"):
        with st.spinner("Running NLP + ML matching…"):
            n = rescreen_job(job_id)
        db.log_activity(user["user_id"], "screen_job", f"{job['job_title']}: {n} resumes")
        st.toast(f"Screened {n} resumes")

    df = db.results_for_job(job_id)
    if df.empty:
        st.info("No results yet — upload resumes and click **Run screening**.")
        return

    with st.container(border=True):
        a, b, c = st.columns([2, 1, 1])
        threshold = a.slider("Shortlist threshold (match score %)", 0, 100, int(config.SHORTLIST_THRESHOLD))
        if b.button("Auto-shortlist", width="stretch", help="Select candidates at or above the threshold, reject the rest"):
            db.auto_shortlist(job_id, threshold)
            db.log_activity(user["user_id"], "auto_shortlist", f"{job['job_title']} @ {threshold}%")
            st.rerun()
        c.download_button("⬇ PDF report", reports.to_pdf(f"Matching Results — {job['job_title']}",
                                                         reports.matching_result_report(job_id)),
                          file_name=f"matching_{job_id}.pdf", mime="application/pdf", width="stretch")

    m = st.columns(4)
    m[0].metric("Screened", len(df))
    m[1].metric("Above threshold", int((df["match_score"] >= threshold).sum()))
    m[2].metric("Selected", int((df["status"] == "Selected").sum()))
    m[3].metric("Top score", f"{df['match_score'].max():.1f}%")

    fig = px.bar(df.head(15), x="match_score", y="name", orientation="h", color="status",
                 color_discrete_map={"Selected": "#16a34a", "Rejected": "#dc2626", "Pending": "#6b7280"},
                 hover_data=["tfidf_score", "skill_score", "experience_score"], height=80 + 32 * min(len(df), 15),
                 labels={"match_score": "Match score (%)", "name": ""})
    fig.add_vline(x=threshold, line_dash="dash", line_color="#f59e0b")
    fig.update_layout(yaxis=dict(autorange="reversed"), margin=dict(l=0, r=10, t=10, b=0))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Ranked candidates")
    edited = st.data_editor(
        df[["rank", "name", "email", "experience_years", "match_score", "tfidf_score", "skill_score",
            "experience_score", "status", "match_id"]],
        hide_index=True, width="stretch", disabled=[c for c in df.columns if c != "status"],
        column_config={
            "match_score": st.column_config.ProgressColumn("Match %", min_value=0, max_value=100, format="%.1f"),
            "tfidf_score": st.column_config.NumberColumn("Content sim. %", format="%.0f"),
            "skill_score": st.column_config.NumberColumn("Skills %", format="%.0f"),
            "experience_score": st.column_config.NumberColumn("Exp. fit %", format="%.0f"),
            "experience_years": st.column_config.NumberColumn("Exp. (yrs)", format="%g"),
            "status": st.column_config.SelectboxColumn("Status", options=["Pending", "Selected", "Rejected"], required=True),
            "match_id": None,
        },
        key=f"editor_{job_id}",
    )
    changed = edited[edited["status"] != df["status"]]
    if not changed.empty:
        for row in changed.itertuples():
            db.set_status(int(row.match_id), row.status)
            db.log_activity(user["user_id"], "set_status", f"{row.name} → {row.status} ({job['job_title']})")
        st.rerun()

    st.subheader("Why this ranking? (explainable matching)")
    for row in df.itertuples():
        with st.expander(f"#{row.rank}  {row.name} — {row.match_score:.1f}%  ·  {row.status}"):
            cols = st.columns(3)
            cols[0].metric("Content similarity (TF-IDF)", f"{row.tfidf_score:.0f}%", help=f"Weight {config.WEIGHT_TFIDF:.0%}")
            cols[1].metric("Skill coverage", f"{row.skill_score:.0f}%", help=f"Weight {config.WEIGHT_SKILLS:.0%}")
            cols[2].metric("Experience fit", f"{row.experience_score:.0f}%", help=f"Weight {config.WEIGHT_EXPERIENCE:.0%}")
            st.markdown("**Matched skills:** " + skill_chips(row.matched_skills), unsafe_allow_html=True)
            st.markdown("**Missing skills:** " + skill_chips(row.missing_skills, missing=True), unsafe_allow_html=True)
            st.caption(f"{row.file_name} · {row.resume_type} resume · {row.experience_years:g} yrs experience · {row.email or ''}")
