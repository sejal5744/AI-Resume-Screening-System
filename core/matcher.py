"""Machine Learning Matching Module.

Score = WEIGHT_TFIDF * TF-IDF cosine similarity (rescaled)
      + WEIGHT_SKILLS * required-skill coverage
      + WEIGHT_EXPERIENCE * experience fit
The per-component scores and matched/missing skills are kept for explainability.
"""
import time

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import config
from core import nlp

# Resume/JD cosine similarity rarely exceeds ~0.6 even for strong matches (resumes contain much
# unrelated text), so the raw value is divided by this ceiling and capped at 1.
TFIDF_CEILING = 0.6


def tfidf_similarities(job_text: str, resume_texts: list[str]) -> list[float]:
    if not resume_texts:
        return []
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, token_pattern=r"(?u)\b[\w+#.]+\b")
    matrix = vectorizer.fit_transform([job_text, *resume_texts])
    return cosine_similarity(matrix[0:1], matrix[1:]).ravel().tolist()


def score_components(similarity: float, resume_skills, job_skills, experience, min_experience) -> dict:
    job_skills, resume_skills = set(job_skills), set(resume_skills)
    tfidf_component = min(similarity / TFIDF_CEILING, 1.0)

    matched = sorted(job_skills & resume_skills)
    missing = sorted(job_skills - resume_skills)
    skill_component = len(matched) / len(job_skills) if job_skills else None

    if min_experience and min_experience > 0:
        exp_component = min((experience or 0) / min_experience, 1.0)
    else:
        exp_component = 1.0

    w_t, w_s, w_e = config.WEIGHT_TFIDF, config.WEIGHT_SKILLS, config.WEIGHT_EXPERIENCE
    if skill_component is None:  # JD lists no recognisable skills: redistribute that weight to TF-IDF
        w_t, w_s, skill_component = w_t + w_s, 0.0, 0.0
    total = w_t * tfidf_component + w_s * skill_component + w_e * exp_component

    return {
        "match_score": round(total * 100, 2),
        "tfidf_score": round(tfidf_component * 100, 2),
        "raw_cosine": round(similarity, 4),
        "skill_score": round(skill_component * 100, 2),
        "experience_score": round(exp_component * 100, 2),
        "matched_skills": matched,
        "missing_skills": missing,
    }


def rank_resumes(job: dict, resumes: list[dict]) -> list[dict]:
    """job: {job_description, skills, min_experience}; resumes: {resume_id, processed_text, skills, experience_years}."""
    start = time.perf_counter()
    job_processed = nlp.preprocess(job["job_description"])
    sims = tfidf_similarities(job_processed, [r["processed_text"] or "" for r in resumes])
    elapsed = (time.perf_counter() - start) / max(len(resumes), 1)

    results = []
    for r, sim in zip(resumes, sims):
        res = score_components(sim, r["skills"], job["skills"], r.get("experience_years"), job.get("min_experience"))
        res.update(resume_id=r["resume_id"], name=r.get("name"), processing_time=round(elapsed, 4))
        results.append(res)
    return sorted(results, key=lambda x: x["match_score"], reverse=True)


def explain(result: dict) -> str:
    parts = [
        f"Content similarity {result['tfidf_score']:.0f}% (weight {config.WEIGHT_TFIDF:.0%})",
        f"skill coverage {result['skill_score']:.0f}% (weight {config.WEIGHT_SKILLS:.0%})",
        f"experience fit {result['experience_score']:.0f}% (weight {config.WEIGHT_EXPERIENCE:.0%})",
    ]
    return "; ".join(parts) + "."
