"""Central configuration for the AI Resume Screening System."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = Path(os.environ.get("RSS_DB_PATH", DATA_DIR / "resume_screening.db"))
SAMPLE_DIR = BASE_DIR / "sample_data"

for _d in (DATA_DIR, UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# File validation (Security: application level)
ALLOWED_DOC_EXT = {".pdf", ".docx", ".txt"}
ALLOWED_IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
ALLOWED_EXT = ALLOWED_DOC_EXT | ALLOWED_IMG_EXT
MAX_FILE_MB = 10

# Tesseract binary: env var wins, otherwise common Windows install locations are probed.
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "")
TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/opt/homebrew/bin/tesseract",
]

# A PDF page with fewer extractable characters than this is treated as scanned.
SCANNED_PDF_MIN_CHARS = 50

# Matching score weights (must sum to 1.0)
WEIGHT_TFIDF = 0.55
WEIGHT_SKILLS = 0.35
WEIGHT_EXPERIENCE = 0.10

# Default shortlist threshold (percentage)
SHORTLIST_THRESHOLD = 60.0

# Default admin seeded on first run — change the password after first login.
DEFAULT_ADMIN_EMAIL = "admin@resumeai.local"
DEFAULT_ADMIN_PASSWORD = "Admin@123"
