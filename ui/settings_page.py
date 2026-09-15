import streamlit as st

import config
from core import auth
from core import database as db
from core import ocr
from ui.common import page_header


def render(user):
    page_header("⚙️ Settings")

    st.subheader("Change password")
    with st.form("pwd", clear_on_submit=True):
        current = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        if st.form_submit_button("Update password"):
            stored = db.get_user_by_email(user["email"])
            if not auth.verify_password(current, stored["password"]):
                st.error("Current password is incorrect.")
            elif new != confirm:
                st.error("New passwords do not match.")
            elif len(new) < 8 or new.isalpha() or new.isdigit():
                st.error("Password must be at least 8 characters and contain letters and digits.")
            else:
                db.update_password(user["user_id"], auth.hash_password(new))
                db.log_activity(user["user_id"], "change_password", "")
                st.success("Password updated.")

    if user["role"] == "admin":
        st.subheader("User management")
        with st.form("new_user", clear_on_submit=True):
            c = st.columns(2)
            name = c[0].text_input("Name")
            email = c[1].text_input("Email")
            c = st.columns(2)
            password = c[0].text_input("Temporary password", type="password")
            role = c[1].selectbox("Role", ["recruiter", "admin"])
            if st.form_submit_button("Create user"):
                err = auth.validate_registration(name, email, password)
                if err:
                    st.error(err)
                else:
                    auth.register(name, email, password, role)
                    db.log_activity(user["user_id"], "create_user", f"{email} ({role})")
                    st.success(f"User {email} created.")
        st.dataframe(db.query_df("SELECT user_id, name, email, role, created_at FROM user ORDER BY user_id"),
                     hide_index=True, width="stretch")

    st.subheader("System")
    st.markdown(
        f"- **Database:** `{config.DB_PATH}`\n"
        f"- **Tesseract OCR:** {'✅ ' + ocr.tesseract_path() if ocr.ocr_available() else '❌ not found'}\n"
        f"- **Score weights:** content {config.WEIGHT_TFIDF:.0%} · skills {config.WEIGHT_SKILLS:.0%} · "
        f"experience {config.WEIGHT_EXPERIENCE:.0%}\n"
        f"- **Accepted formats:** {', '.join(sorted(config.ALLOWED_EXT))} (≤ {config.MAX_FILE_MB} MB)"
    )
