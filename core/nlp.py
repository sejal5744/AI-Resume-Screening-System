"""NLP Processing Module.

Text preprocessing (tokenization, stopword removal, lemmatization) and information
extraction (name, email, phone, skills, experience, education, sections).
spaCy is used when its English model is installed; otherwise NLTK / plain regex fallbacks apply.
"""
import re
from datetime import datetime
from functools import lru_cache

from core.skills import all_aliases

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<![\w.])(?:\+?\d{1,3}[\s.-]?)?\(?\d{3,5}\)?[\s.-]?\d{3,5}(?:[\s.-]?\d{2,5})?(?![\w.])")
YEARS_RE = re.compile(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+\w+){0,3}?\s+experience", re.I)
YEARS_SIMPLE_RE = re.compile(r"experience\s*(?:of|:)?\s*(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)", re.I)
MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
RANGE_RE = re.compile(
    rf"(?:(?:{MONTHS})[a-z]*\.?\s+)?((?:19|20)\d{{2}})\s*(?:-|–|—|to)\s*(?:(?:{MONTHS})[a-z]*\.?\s+)?((?:19|20)\d{{2}}|present|current|now|till date)",
    re.I,
)

SECTION_HEADINGS = {
    "contact": ["contact", "personal details", "personal information"],
    "summary": ["summary", "objective", "profile", "about me", "career objective"],
    "education": ["education", "academic", "qualification"],
    "experience": ["experience", "employment", "work history", "internship"],
    "skills": ["skills", "technical skills", "core competencies", "technologies"],
    "projects": ["projects", "project work"],
    "certifications": ["certification", "certificates", "courses", "training"],
    "achievements": ["achievements", "awards", "accomplishments"],
}

DEGREES = [
    ("PhD", r"\bph\.?\s?d\b|doctorate"),
    ("M.Tech", r"\bm\.?\s?tech\b|master of technology"),
    ("MCA", r"\bm\.?c\.?a\b|master of computer applications"),
    ("MBA", r"\bm\.?b\.?a\b"),
    ("M.Sc", r"\bm\.?\s?sc\b|master of science"),
    ("B.Tech", r"\bb\.?\s?tech\b|bachelor of technology"),
    ("B.E.", r"\bb\.\s?e\.?(?=[\s,])|bachelor of engineering"),
    ("BCA", r"\bb\.?c\.?a\b|bachelor of computer applications"),
    ("B.Sc", r"\bb\.?\s?sc\b|bachelor of science"),
    ("B.Com", r"\bb\.?\s?com\b|bachelor of commerce"),
    ("Diploma", r"\bdiploma\b"),
]

_FALLBACK_STOPWORDS = set(
    """a about above after again against all am an and any are as at be because been before being below
    between both but by can did do does doing down during each few for from further had has have having he
    her here hers herself him himself his how i if in into is it its itself just me more most my myself no
    nor not now of off on once only or other our ours ourselves out over own same she should so some such
    than that the their theirs them themselves then there these they this those through to too under until
    up very was we were what when where which while who whom why will with you your yours yourself""".split()
)


@lru_cache(maxsize=1)
def _spacy():
    try:
        import spacy

        return spacy.load("en_core_web_sm")
    except Exception:
        return None


@lru_cache(maxsize=1)
def stopwords() -> frozenset:
    try:
        from nltk.corpus import stopwords as sw

        words = set(sw.words("english"))
    except Exception:
        words = set(_FALLBACK_STOPWORDS)
    # Domain noise that carries no matching signal
    words |= {"resume", "curriculum", "vitae", "cv", "name", "email", "phone", "mobile", "address", "etc"}
    return frozenset(words)


@lru_cache(maxsize=1)
def _skill_patterns():
    pats = []
    for alias, canonical in all_aliases():
        esc = re.escape(alias)
        # word boundaries that also work for symbols like c++, c#, .net, node.js
        pats.append((re.compile(rf"(?<![\w+#.]){esc}(?![\w+#])", re.I), canonical))
    return pats


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[•●▪‣⁃]", " ", text)  # bullet glyphs
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z0-9+#.]*[a-z0-9+#]|[a-z]", text.lower())


def preprocess(text: str) -> str:
    """Tokenize, remove stopwords, lemmatize. Returns space-joined tokens for TF-IDF."""
    sw = stopwords()
    nlp = _spacy()
    if nlp is not None:
        doc = nlp(text.lower()[:200000], disable=["parser", "ner"])
        tokens = [
            (t.lemma_ if t.lemma_ and t.lemma_ != "-PRON-" else t.text)
            for t in doc
            if not t.is_space and not t.is_punct and not t.like_num and t.text not in sw
        ]
    else:
        try:
            from nltk.stem import WordNetLemmatizer

            lem = WordNetLemmatizer()
            tokens = [lem.lemmatize(t) for t in tokenize(text) if t not in sw]
        except Exception:
            tokens = [t for t in tokenize(text) if t not in sw]
    tokens = [t.strip(".") for t in tokens if len(t.strip(".")) > 1 or t in {"c", "r"}]
    # Canonical skills are appended so aliases (e.g. "ml" / "machine learning") share features.
    tokens += [s.replace(" ", "_") for s in extract_skills(text)]
    return " ".join(tokens)


def extract_email(text: str) -> str | None:
    m = EMAIL_RE.search(text)
    return m.group(0) if m else None


def extract_phone(text: str) -> str | None:
    for m in PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 10 <= len(digits) <= 13:
            return m.group(0).strip()
    return None


def extract_name(text: str) -> str | None:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    heading_words = {w for hs in SECTION_HEADINGS.values() for h in hs for w in h.split()} | {"resume", "cv", "curriculum", "vitae"}
    for line in lines[:6]:
        candidate = re.sub(r"^(name\s*[:\-]\s*)", "", line, flags=re.I)
        words = candidate.split()
        if (
            1 < len(words) <= 4
            and not EMAIL_RE.search(candidate)
            and not re.search(r"\d", candidate)
            and all(re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", w) for w in words)
            and not {w.lower() for w in words} & heading_words
        ):
            return " ".join(w.capitalize() if w.isupper() or w.islower() else w for w in words)
    nlp = _spacy()
    if nlp is not None:
        for ent in nlp("\n".join(lines[:15])).ents:
            if ent.label_ == "PERSON" and 1 < len(ent.text.split()) <= 4:
                return ent.text.strip()
    return None


def extract_skills(text: str) -> list[str]:
    found = set()
    for pat, canonical in _skill_patterns():
        if canonical not in found and pat.search(text):
            found.add(canonical)
    # Single-letter languages are too ambiguous unless clearly listed as languages
    for short in ("c", "r", "go"):
        if short in found and not re.search(rf"(?:languages?|skills?)[^\n]{{0,80}}(?<![\w+#.]){short}(?![\w+#])", text, re.I):
            found.discard(short)
    return sorted(found)


def extract_experience_years(text: str) -> float:
    explicit = [float(x) for x in YEARS_RE.findall(text) + YEARS_SIMPLE_RE.findall(text)]
    if explicit:
        return min(max(explicit), 50.0)
    this_year = datetime.now().year
    # Only date ranges inside the experience section count, to avoid education years.
    section = get_sections(text).get("experience", "")
    intervals = []
    for start, end in RANGE_RE.findall(section):
        s = int(start)
        e = this_year if not end[:1].isdigit() else int(end)
        if 1970 <= s <= e <= this_year:
            intervals.append((s, e))
    if not intervals:
        return 0.0
    intervals.sort()
    merged = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return float(sum(e - s for s, e in merged))


def extract_education(text: str) -> str | None:
    found = [label for label, pat in DEGREES if re.search(pat, text, re.I)]
    return ", ".join(found) if found else None


def get_sections(text: str) -> dict[str, str]:
    """Split resume text into sections keyed by the canonical heading names."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        stripped = line.strip().rstrip(":").lower()
        key = None
        if 0 < len(stripped) <= 40:
            for name, heads in SECTION_HEADINGS.items():
                if any(stripped == h or stripped.startswith(h + " ") or stripped.endswith(" " + h) for h in heads):
                    key = name
                    break
        if key:
            current = key
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line)
    return {k: "\n".join(v) for k, v in sections.items()}


def structure_score(text: str) -> float:
    """0-100 score for how well-structured a resume's content is (sections, contact info, length)."""
    sections = get_sections(text)
    important = ["education", "experience", "skills", "projects", "summary"]
    score = 50 * sum(1 for s in important if s in sections) / len(important)
    score += 10 if extract_email(text) else 0
    score += 10 if extract_phone(text) else 0
    words = len(text.split())
    score += 20 if 150 <= words <= 1200 else (10 if words >= 60 else 0)
    score += 10 if len(extract_skills(text)) >= 5 else 5 * (len(extract_skills(text)) > 0)
    return round(min(score, 100.0), 1)


def analyze_resume(text: str) -> dict:
    text = clean_text(text)
    return {
        "resume_text": text,
        "processed_text": preprocess(text),
        "name": extract_name(text),
        "email": extract_email(text),
        "phone": extract_phone(text),
        "skills": extract_skills(text),
        "experience_years": extract_experience_years(text),
        "education": extract_education(text),
        "sections": list(get_sections(text).keys()),
        "structure_score": structure_score(text),
    }
