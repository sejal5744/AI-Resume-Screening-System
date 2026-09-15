# AI Resume Screening System

An AI-powered resume screening system . It uses **NLP**, **Machine Learning** and **Computer Vision / OCR** to parse resumes, match them to job descriptions, rank candidates and generate reports.

| Layer | Technology |
|---|---|
| Frontend | Streamlit (+ Plotly charts) |
| Backend | Python |
| NLP | spaCy (lemmatization, NER), NLTK stopwords, regex extractors |
| ML matching | scikit-learn TF-IDF + cosine similarity, skill coverage, experience fit |
| Computer Vision & OCR | OpenCV (denoise, deskew, binarise, layout analysis) + Tesseract via pytesseract |
| Documents | PyMuPDF (PDF), python-docx (DOCX) |
| Database | SQLite (`data/resume_screening.db`) |
| Security | bcrypt password hashing, session auth, file type/size/magic-byte validation, parameterised SQL |
| Reports | pandas + ReportLab (CSV / PDF export) |

## Quick start

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet')"
python -m streamlit run app.py
```

Open http://localhost:8501 and sign in with the seeded admin account:

- **Email:** `admin@resumeai.local`
- **Password:** `Admin@123` (change it under **Settings**)

On an empty database, the dashboard offers a **Load sample data** button (6 resumes in PDF/DOCX/TXT/PNG and 3 job postings).

### OCR for scanned resumes (optional but recommended)

Image resumes and scanned PDFs need the Tesseract engine:

- **Windows:** install from https://github.com/UB-Mannheim/tesseract/wiki (default path is auto-detected) or `winget install UB-Mannheim.TesseractOCR`
- **Ubuntu:** `sudo apt install tesseract-ocr`
- **macOS:** `brew install tesseract`

If it is installed somewhere else, set `TESSERACT_CMD` to the full path of the executable. Without Tesseract, everything else works and image uploads are rejected with a clear message.

## Modules (synopsis §9.1)

| # | Module | Code |
|---|---|---|
| 1 | User Management | `core/auth.py`, `ui/settings_page.py` |
| 2 | Resume Upload & Parsing | `core/parser.py`, `ui/upload.py` |
| 3 | NLP Processing | `core/nlp.py`, `core/skills.py` |
| 4 | Machine Learning Matching | `core/matcher.py`, `ui/screening.py` |
| 5 | Computer Vision & OCR | `core/ocr.py` |
| 6 | Database | `core/database.py` |
| 7 | Result & Reporting | `core/reports.py`, `ui/reports_page.py`, `ui/dashboard.py` |

## How matching works

```
match_score = 0.55 × TF-IDF content similarity   (cosine of lemmatized resume vs JD, rescaled)
            + 0.35 × required-skill coverage      (matched JD skills / all JD skills)
            + 0.10 × experience fit               (candidate years / required years, capped at 1)
```

Each result stores its component scores and matched/missing skills, so the **Screening & Ranking** page can explain every ranking. Weights and the default shortlist threshold are in `config.py`.

Pipeline: upload → validation → text extraction (or OpenCV preprocessing + Tesseract OCR for scanned files) → NLP (tokenize, remove stopwords, lemmatize; extract name, email, phone, skills, experience, education, sections) → SQLite → TF-IDF matching → ranking → shortlist → reports.

## Database (synopsis §8)

`user`, `candidate`, `skill`, `candidate_skill`, `resume` (incl. `resume_type`, `ocr_confidence`, `layout_score`), `job_posting`, `job_skill`, `matching_result` (`match_score`, `status`), plus `activity_log` for the User Activity and System Performance reports.

## Reports (synopsis §9.4)

User Activity (admin only), Candidate, Resume Analysis, Matching Result, Job Posting and System Performance. Each report can be exported as CSV or PDF.

## Project layout

```
app.py                 Streamlit entry point (login + navigation)
config.py              paths, weights, limits, Tesseract lookup
core/                  backend: auth, database, parser, nlp, ocr, matcher, reports, seed
ui/                    Streamlit pages
scripts/generate_samples.py   builds the demo dataset in sample_data/
tests/test_pipeline.py        end-to-end tests (python -m pytest -q)
```

## Security notes

- Passwords are hashed with bcrypt and never stored in plain text. Every page except login requires an authenticated session.
- Uploads are checked against an extension whitelist, a 10 MB size limit and magic bytes. Uploaded files are parsed in memory and never executed.
- All SQL uses bound parameters. Foreign keys with cascades keep the data consistent.
- The app runs on localhost by default. Use HTTPS (a reverse proxy) for any real deployment.
