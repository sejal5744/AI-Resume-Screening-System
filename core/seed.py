"""Load the sample dataset (sample_data/) into the database for demos."""
import json

import config
from core import database as db
from core import matcher, nlp, ocr, parser


def load_samples(user_id=None) -> dict:
    res_dir = config.SAMPLE_DIR / "resumes"
    jobs_file = config.SAMPLE_DIR / "jobs" / "jobs.json"
    if not res_dir.exists() or not jobs_file.exists():
        from scripts import generate_samples

        generate_samples.main()

    summary = {"resumes": 0, "jobs": 0, "skipped": []}
    existing_files = set(db.list_resumes()["file_name"])
    for path in sorted(res_dir.iterdir()):
        if path.name in existing_files:
            continue
        if path.suffix.lower() in config.ALLOWED_IMG_EXT and not ocr.ocr_available():
            summary["skipped"].append(f"{path.name} (Tesseract OCR not installed)")
            continue
        try:
            info = parser.process_resume(path.name, path.read_bytes())
            db.add_candidate_with_resume(info, user_id)
            summary["resumes"] += 1
        except Exception as exc:  # keep loading the rest
            summary["skipped"].append(f"{path.name} ({exc})")

    existing_jobs = set(db.list_jobs()["job_title"])
    for job in json.loads(jobs_file.read_text(encoding="utf-8")):
        if job["job_title"] in existing_jobs:
            continue
        skills = nlp.extract_skills(job["job_description"])
        db.add_job(user_id, job["job_title"], job["job_description"], skills, job["min_experience"])
        summary["jobs"] += 1

    resumes = db.resumes_for_matching()
    for job_id in db.list_jobs()["job_id"]:
        job = db.get_job(int(job_id))
        for res in matcher.rank_resumes(job, resumes):
            db.save_match(res["resume_id"], job["job_id"], res)

    db.log_activity(user_id, "load_samples", json.dumps({k: v for k, v in summary.items() if k != "skipped"}))
    return summary
