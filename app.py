"""AI Resume Screening System — Streamlit entry point.

Run:  streamlit run app.py
"""
import streamlit as st

import config
from core import auth
from core import database as db
from ui import candidates, dashboard, jobs, reports_page, screening, settings_page, upload
from ui.common import inject_css

st.set_page_config(page_title="AI Resume Screening System", page_icon="🧠", layout="wide")
inject_css()


@st.cache_resource
def bootstrap():
    db.init_db()
    auth.ensure_default_admin()
    return True


bootstrap()


def login_view():
    left, mid, right = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<div class='hero'><h1>🧠 AI Resume Screening</h1>"
                    "<p>NLP · Machine Learning · Computer Vision (OCR)</p></div>", unsafe_allow_html=True)
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
        if submitted:
            user = auth.login(email, password)
            if user:
                st.session_state.user = user
                st.rerun()
            st.error("Invalid email or password.")
        if db.get_user_by_email(config.DEFAULT_ADMIN_EMAIL):
            st.caption(f"First run? Sign in with **{config.DEFAULT_ADMIN_EMAIL}** / **{config.DEFAULT_ADMIN_PASSWORD}** "
                       "and change the password under Settings.")


def main():
    user = st.session_state.get("user")
    if not user:
        login_view()
        return

    pages = {
        "Dashboard": ("📊", dashboard.render),
        "Job Postings": ("💼", jobs.render),
        "Upload Resumes": ("📤", upload.render),
        "Screening & Ranking": ("🏆", screening.render),
        "Candidates": ("👥", candidates.render),
        "Reports": ("📑", reports_page.render),
        "Settings": ("⚙️", settings_page.render),
    }
    with st.sidebar:
        st.markdown(f"### 🧠 Resume Screening\n**{user['name']}**  \n<small>{user['email']} · {user['role']}</small>",
                    unsafe_allow_html=True)
        st.divider()
        page = st.radio("Navigation", list(pages), format_func=lambda p: f"{pages[p][0]}  {p}",
                        label_visibility="collapsed", key="nav")
        st.divider()
        if st.button("Sign out", width="stretch"):
            db.log_activity(user["user_id"], "logout", "")
            st.session_state.clear()
            st.rerun()
    pages[page][1](user)


main()
