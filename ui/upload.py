import streamlit as st

import config
from core import database as db
from core import ocr, parser
from ui.common import page_header, rescreen_all, skill_chips


def render(user):
    page_header("📤 Upload Resumes",
                "PDF and DOCX files are parsed directly; scanned PDFs and images go through OpenCV preprocessing + Tesseract OCR.")

    if not ocr.ocr_available():
        st.warning("Tesseract OCR is not installed, so image files and scanned PDFs will be rejected. "
                   "Text PDFs, DOCX and TXT work normally.", icon="⚠️")

    files = st.file_uploader(
        f"Select resumes (max {config.MAX_FILE_MB} MB each)",
        type=[e.lstrip(".") for e in sorted(config.ALLOWED_EXT)],
        accept_multiple_files=True,
    )
    auto_screen = st.checkbox("Screen against all job postings after upload", value=True)

    if st.button("Process resumes", type="primary", disabled=not files):
        progress = st.progress(0.0, text="Starting…")
        processed, errors = [], []
        for i, f in enumerate(files, start=1):
            progress.progress((i - 1) / len(files), text=f"Processing {f.name} ({i}/{len(files)})")
            try:
                info = parser.process_resume(f.name, f.getvalue())
                info["resume_id"] = db.add_candidate_with_resume(info, user["user_id"])
                processed.append(info)
            except (parser.InvalidFileError, ocr.OCRUnavailableError, ValueError) as exc:
                errors.append(str(exc))
            except Exception as exc:  # never crash the page on a malformed document
                errors.append(f"{f.name}: unexpected error while parsing ({type(exc).__name__}).")
        progress.progress(1.0, text="Done")

        if processed:
            db.log_activity(user["user_id"], "upload_resumes", f"{len(processed)} file(s)")
            if auto_screen and not db.list_jobs().empty:
                rescreen_all()
        st.session_state.last_upload = {"processed": processed, "errors": errors}

    result = st.session_state.get("last_upload")
    if not result:
        return
    if result["processed"]:
        st.success(f"{len(result['processed'])} resume(s) processed and stored.")
    for err in result["errors"]:
        st.error(err)

    for info in result["processed"]:
        with st.container(border=True):
            cols = st.columns([2, 1.4, 1, 1, 1.2])
            cols[0].markdown(f"**{info['name']}**  \n{info.get('email') or '—'} · {info.get('phone') or '—'}  \n"
                             f"<small>{info['file_name']}</small>", unsafe_allow_html=True)
            cols[1].metric("Type", info["resume_type"].title())
            cols[2].metric("Experience", f"{info['experience_years']:g} yrs")
            cols[3].metric("Layout score", f"{info['layout_score']:.0f}")
            cols[4].metric("OCR confidence", f"{info['ocr_confidence']:.0f}%" if info.get("ocr_confidence") is not None else "n/a")
            st.markdown(f"**Education:** {info.get('education') or '—'} &nbsp; · &nbsp; "
                        f"**Sections:** {', '.join(info['sections']) or '—'}")
            st.markdown(skill_chips(info["skills"]), unsafe_allow_html=True)
            with st.expander("Extracted text / NLP output"):
                t1, t2 = st.tabs(["Raw text", "Preprocessed tokens (tokenized · stopwords removed · lemmatized)"])
                t1.text(info["resume_text"][:5000])
                t2.text(info["processed_text"][:5000])
