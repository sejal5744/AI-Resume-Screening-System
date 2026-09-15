"""Generate a demo dataset: resumes in PDF, DOCX, TXT and scanned-image formats plus job descriptions.

Usage:  python scripts/generate_samples.py
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

import config  # noqa: E402

RESUMES = {
    "aarav_sharma": ("pdf", """Aarav Sharma
aarav.sharma@example.com | +91 98765 43210 | Bengaluru

SUMMARY
Machine learning engineer with 4 years of experience building NLP and computer vision products.

EXPERIENCE
ML Engineer, InsightAI Labs (Jan 2021 - Present)
- Built resume parsing and candidate ranking service using spaCy, NLTK and scikit-learn (TF-IDF, cosine similarity).
- Deployed models with FastAPI and Docker on AWS; CI/CD with GitHub Actions.
Data Scientist Intern, DataWorks (Jun 2020 - Dec 2020)
- Created OCR pipeline with OpenCV and Tesseract for invoice digitisation.

SKILLS
Python, Machine Learning, Deep Learning, NLP, OpenCV, Tesseract, PyTorch, TensorFlow, Pandas, NumPy,
Scikit-learn, SQL, SQLite, Docker, AWS, Git, REST API, Streamlit

EDUCATION
B.Tech in Computer Science, VIT University, 2020

PROJECTS
AI Resume Screener - Streamlit app ranking resumes against job descriptions.
"""),
    "priya_verma": ("docx", """Priya Verma
Email: priya.verma@example.com
Phone: +91 91234 56789

CAREER OBJECTIVE
Data analyst passionate about turning data into business decisions.

WORK EXPERIENCE
Data Analyst, RetailMart (2022 - Present)
- Built Power BI and Tableau dashboards for sales analytics.
- Automated ETL jobs with Python, Pandas and MySQL.

TECHNICAL SKILLS
Python, SQL, MySQL, Excel, Power BI, Tableau, Pandas, NumPy, Statistics, Data Analysis, Matplotlib

EDUCATION
MCA, IGNOU, 2022
BCA, Delhi University, 2019

CERTIFICATIONS
Google Data Analytics Professional Certificate
"""),
    "rahul_mehta": ("pdf", """Rahul Mehta
rahul.mehta@example.com  |  +91 99887 76655

PROFILE
Full stack developer with 6 years of experience delivering scalable web applications.

EXPERIENCE
Senior Software Engineer, CloudNine Tech (2019 - Present)
- Developed microservices with Node.js, Express and React; PostgreSQL and Redis.
- Containerised services with Docker and Kubernetes; Jenkins CI/CD pipelines on Azure.
Software Engineer, WebCraft (2017 - 2019)
- Built REST APIs in Django and JavaScript front ends.

SKILLS
JavaScript, TypeScript, React, Node.js, Express, Django, Python, PostgreSQL, MongoDB, Redis, Docker,
Kubernetes, Azure, Git, HTML, CSS, Agile

EDUCATION
B.E. Information Technology, Pune University, 2017
"""),
    "sneha_iyer": ("txt", """SNEHA IYER
sneha.iyer@example.com
+91 90000 11122

OBJECTIVE
Fresh graduate seeking an entry-level role in software development.

EDUCATION
B.Sc Computer Science, Madras University, 2025

PROJECTS
Library Management System - Java, MySQL
Weather App - HTML, CSS, JavaScript

SKILLS
Java, C++, HTML, CSS, JavaScript, MySQL, Data Structures, Communication, Teamwork

INTERNSHIP
Web Development Intern, StartupHub (May 2024 - Jul 2024)
"""),
    "vikram_singh": ("png", """Vikram Singh
vikram.singh@example.com
+91 98111 22233

SUMMARY
Computer vision engineer with 3 years of experience.

EXPERIENCE
CV Engineer, VisionTech (2022 - Present)
Built OCR and document image processing with OpenCV,
Tesseract and PyTorch. Deployed on Docker.

SKILLS
Python, OpenCV, Tesseract, PyTorch, Deep Learning,
Machine Learning, NumPy, Docker, Linux, Git

EDUCATION
M.Tech Computer Science, IIT Delhi, 2022
"""),
    "neha_kapoor": ("pdf", """Neha Kapoor
neha.kapoor@example.com | +91 97654 32109

SUMMARY
Digital marketing specialist with 5 years of experience in SEO and campaign analytics.

EXPERIENCE
Marketing Manager, BrandBoost (2020 - Present)
- Led SEO and digital marketing campaigns; managed a team of 6.
- Reported KPIs using Excel and Google Analytics.

SKILLS
SEO, Digital Marketing, Excel, Communication, Leadership, Project Management, Photoshop

EDUCATION
MBA Marketing, Symbiosis, 2019
"""),
}

JOBS = [
    {
        "job_title": "Machine Learning Engineer (NLP / CV)",
        "min_experience": 2,
        "job_description": """We are hiring a Machine Learning Engineer to build our AI resume screening platform.
Responsibilities: design NLP pipelines for text extraction and entity recognition, build ranking models
with scikit-learn (TF-IDF, similarity measures), implement OCR for scanned documents using OpenCV and
Tesseract, and deploy models as REST APIs with Docker on AWS.
Requirements: 2+ years of experience with Python, Machine Learning, NLP, OpenCV, Pandas, NumPy,
Scikit-learn, SQL and Git. Experience with PyTorch or TensorFlow is a plus.""",
    },
    {
        "job_title": "Data Analyst",
        "min_experience": 1,
        "job_description": """Looking for a Data Analyst to analyse sales and customer data and build dashboards.
Must know SQL, Excel, Python (Pandas), statistics and data visualisation with Power BI or Tableau.
1+ year of experience in data analysis. Good communication skills required.""",
    },
    {
        "job_title": "Full Stack Developer",
        "min_experience": 3,
        "job_description": """Full Stack Developer to build scalable web applications. Tech stack: React, Node.js,
Express, JavaScript/TypeScript, PostgreSQL or MongoDB, REST API design, Docker, Git and CI/CD.
3+ years of experience required. Cloud experience (AWS or Azure) and Agile practices preferred.""",
    },
]


def write_pdf(path: Path, text: str):
    c = canvas.Canvas(str(path), pagesize=A4)
    y = A4[1] - 2 * cm
    for i, line in enumerate(text.strip().splitlines()):
        is_heading = line.isupper() and line.strip() and i > 0
        c.setFont("Helvetica-Bold", 16 if i == 0 else 11) if (i == 0 or is_heading) else c.setFont("Helvetica", 10)
        c.drawString(2 * cm, y, line)
        y -= 0.62 * cm if (i == 0 or is_heading) else 0.5 * cm
        if y < 2 * cm:
            c.showPage()
            y = A4[1] - 2 * cm
    c.save()


def write_docx(path: Path, text: str):
    import docx

    d = docx.Document()
    lines = text.strip().splitlines()
    d.add_heading(lines[0], level=0)
    for line in lines[1:]:
        if line.isupper() and line.strip():
            d.add_heading(line.title(), level=1)
        elif line.strip():
            d.add_paragraph(line)
    d.save(str(path))


def write_scanned_png(path: Path, text: str):
    """Render text as a slightly rotated, noisy 'scan' to exercise the OpenCV + OCR pipeline."""
    w, h = 1700, 2200
    img = Image.new("L", (w, h), 245)
    draw = ImageDraw.Draw(img)
    font = None
    for name in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            font = ImageFont.truetype(name, 34)
            bold = ImageFont.truetype(name, 46)
            break
        except OSError:
            continue
    if font is None:
        font = bold = ImageFont.load_default()
    y = 140
    for i, line in enumerate(text.strip().splitlines()):
        draw.text((150, y), line, fill=25, font=bold if i == 0 else font)
        y += 64 if i == 0 else 50
    rng = random.Random(7)
    for _ in range(4000):  # speckle noise
        draw.point((rng.randrange(w), rng.randrange(h)), fill=rng.randrange(120, 200))
    img = img.rotate(1.2, fillcolor=245, resample=Image.BICUBIC).filter(ImageFilter.GaussianBlur(0.6))
    img.save(path)


def main():
    res_dir = config.SAMPLE_DIR / "resumes"
    job_dir = config.SAMPLE_DIR / "jobs"
    res_dir.mkdir(parents=True, exist_ok=True)
    job_dir.mkdir(parents=True, exist_ok=True)

    writers = {"pdf": write_pdf, "docx": write_docx, "png": write_scanned_png}
    for stem, (fmt, text) in RESUMES.items():
        path = res_dir / f"{stem}.{fmt}"
        if fmt == "txt":
            path.write_text(text.strip(), encoding="utf-8")
        else:
            writers[fmt](path, text)
        print("wrote", path.relative_to(config.BASE_DIR))

    (job_dir / "jobs.json").write_text(json.dumps(JOBS, indent=2), encoding="utf-8")
    print("wrote", (job_dir / "jobs.json").relative_to(config.BASE_DIR))


if __name__ == "__main__":
    main()
