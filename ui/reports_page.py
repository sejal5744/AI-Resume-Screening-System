from datetime import datetime

import streamlit as st

from core import database as db
from core import reports
from ui.common import page_header


def render(user):
    page_header("📑 Reports", "Generate and export the system reports as CSV or PDF.")
    name = st.selectbox("Report", list(reports.REPORTS))
    if name == "User Activity Report" and user["role"] != "admin":
        st.warning("The User Activity Report is available to administrators only.")
        return

    df = reports.REPORTS[name]()
    st.caption(f"{len(df)} record(s)")
    st.dataframe(df, hide_index=True, width="stretch")

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    slug = name.lower().replace(" ", "_")
    a, b, _ = st.columns([1, 1, 3])
    if a.download_button("⬇ Download CSV", reports.to_csv(df), file_name=f"{slug}_{stamp}.csv", mime="text/csv",
                         width="stretch"):
        db.log_activity(user["user_id"], "export_report", f"{name} (CSV)")
    if b.download_button("⬇ Download PDF", reports.to_pdf(name, df), file_name=f"{slug}_{stamp}.pdf",
                         mime="application/pdf", width="stretch"):
        db.log_activity(user["user_id"], "export_report", f"{name} (PDF)")
