"""End-to-end tests for parsing, NLP, matching, database and reports.

Run:  python -m pytest -q
"""
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def temp_db(tmp_path_factory):
    os.environ["RSS_DB_PATH"] = str(tmp_path_factory.mktemp("db") / "test.db")
    import importlib

    import config

    importlib.reload(config)
    from core import database

    database.init_db()
    yield


def test_nlp_extraction():
    from core import nlp

    text = """John Doe
john.doe@mail.com | +91 98765 43210
EXPERIENCE
Engineer, Acme (2019 - 2023)
SKILLS
Python, ML, scikit-learn, Docker, C++
EDUCATION
B.Tech Computer Science"""
    a = nlp.analyze_resume(text)
    assert a["name"] == "John Doe"
    assert a["email"] == "john.doe@mail.com"
    assert a["phone"] == "+91 98765 43210"
    assert {"python", "machine learning", "scikit-learn", "docker", "c++"} <= set(a["skills"])
    assert a["experience_years"] == 4
    assert a["education"] == "B.Tech"
    assert "experience" in a["processed_text"] or "engineer" in a["processed_text"]
    assert " the " not in f" {a['processed_text']} "  # stopwords removed


def test_explicit_experience_and_ambiguous_skills():
    from core import nlp

    assert nlp.extract_experience_years("I have 5+ years of professional experience in sales") == 5
    assert "c" not in nlp.extract_skills("Plan C was chosen. Go ahead.")
    assert "go" not in nlp.extract_skills("Go ahead with the plan")


def test_file_validation():
    from core import parser

    with pytest.raises(parser.InvalidFileError):
        parser.validate_file("evil.exe", b"MZ....")
    with pytest.raises(parser.InvalidFileError):
        parser.validate_file("fake.pdf", b"not a pdf")
    parser.validate_file("ok.txt", b"hello world")


def test_sample_formats_parse():
    from scripts import generate_samples

    generate_samples.main()
    from core import parser

    res_dir = ROOT / "sample_data" / "resumes"
    for name in ("aarav_sharma.pdf", "priya_verma.docx", "sneha_iyer.txt"):
        info = parser.process_resume(name, (res_dir / name).read_bytes())
        assert info["resume_type"] == "text"
        assert info["email"] and info["skills"]


def test_opencv_preprocessing_and_layout_score():
    from core import ocr

    data = (ROOT / "sample_data" / "resumes" / "vikram_singh.png").read_bytes()
    img = ocr.decode_image(data)
    binary, meta = ocr.preprocess(img)
    assert binary.ndim == 2 and set(np.unique(binary)) <= {0, 255}
    assert abs(meta["skew_angle"]) < 5
    assert 0 <= ocr.layout_score(binary, meta["skew_angle"]) <= 100


@pytest.mark.parametrize("degrees", [-5, -1.5, 1.5, 5])
def test_deskew_corrects_both_directions(degrees):
    import cv2
    from PIL import Image

    from core import ocr

    page = np.full((1200, 1200), 245, np.uint8)
    for i in range(16):
        cv2.putText(page, "The quick brown fox jumps over the lazy dog", (60, 100 + i * 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, 20, 2)
    skewed = np.array(Image.fromarray(page).rotate(degrees, fillcolor=245, resample=Image.BICUBIC))
    fixed, correction = ocr.deskew(skewed)
    assert correction == pytest.approx(-degrees, abs=0.3)
    assert abs(ocr.estimate_skew(fixed)) <= 0.3


@pytest.mark.skipif("not __import__('core.ocr', fromlist=['x']).ocr_available()", reason="Tesseract not installed")
def test_ocr_scanned_resume():
    from core import parser

    data = (ROOT / "sample_data" / "resumes" / "vikram_singh.png").read_bytes()
    info = parser.process_resume("vikram_singh.png", data)
    assert info["resume_type"] == "scanned"
    assert "opencv" in info["skills"]


def test_matching_ranks_relevant_candidate_first():
    from core import matcher, nlp

    job = {"job_description": "Python machine learning engineer with NLP, scikit-learn and OpenCV",
           "skills": ["python", "machine learning", "natural language processing", "scikit-learn", "opencv"],
           "min_experience": 2}
    good = "Python ML engineer. Built NLP models using scikit-learn and OpenCV. 3 years of experience."
    bad = "Accountant skilled in Tally and GST filing with 10 years of experience."
    resumes = [
        {"resume_id": i, "processed_text": nlp.preprocess(t), "skills": nlp.extract_skills(t),
         "experience_years": nlp.extract_experience_years(t)}
        for i, t in enumerate([bad, good])
    ]
    ranked = matcher.rank_resumes(job, resumes)
    assert ranked[0]["resume_id"] == 1
    assert ranked[0]["match_score"] > 60 > ranked[1]["match_score"]
    assert ranked[0]["missing_skills"] == []


def test_auth_and_database_flow():
    from core import auth, reports, seed
    from core import database as db

    uid = auth.register("Test Admin", "t@example.com", "Secret123", "admin")
    assert db.get_user_by_email("t@example.com")["password"] != "Secret123"  # hashed
    assert auth.login("t@example.com", "Secret123")["user_id"] == uid
    assert auth.login("t@example.com", "wrong") is None
    assert auth.validate_registration("x", "t@example.com", "Secret123")  # duplicate

    summary = seed.load_samples(uid)
    assert summary["resumes"] >= 5 and summary["jobs"] == 3

    for job in db.list_jobs().itertuples():
        top = db.results_for_job(int(job.job_id)).iloc[0]
        expected = {"Machine Learning Engineer (NLP / CV)": "Aarav Sharma",
                    "Data Analyst": "Priya Verma", "Full Stack Developer": "Rahul Mehta"}[job.job_title]
        assert top["name"] == expected

    ml_job = int(db.list_jobs().query("job_title == 'Data Analyst'")["job_id"].iloc[0])
    db.auto_shortlist(ml_job, 60)
    res = db.results_for_job(ml_job)
    assert set(res[res.match_score >= 60].status) == {"Selected"}

    for name, fn in reports.REPORTS.items():
        df = fn()
        assert reports.to_pdf(name, df).startswith(b"%PDF")
        assert reports.to_csv(df)
