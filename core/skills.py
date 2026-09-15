"""Skill vocabulary used for skill extraction.

Keys are canonical skill names (stored in the SKILL table); values are extra aliases.
Matching is case-insensitive and respects word boundaries.
"""

SKILLS: dict[str, list[str]] = {
    # Programming languages
    "python": [], "java": [], "javascript": ["js", "ecmascript"], "typescript": [],
    "c": [], "c++": ["cpp"], "c#": ["csharp"], "go": ["golang"], "rust": [], "kotlin": [],
    "swift": [], "php": [], "ruby": [], "r": [], "scala": [], "matlab": [], "bash": ["shell scripting"],
    "sql": [], "html": ["html5"], "css": ["css3"], "dart": [],
    # Web / frameworks
    "react": ["react.js", "reactjs"], "angular": ["angularjs"], "vue": ["vue.js", "vuejs"],
    "next.js": ["nextjs"], "node.js": ["nodejs", "node"], "express": ["express.js"],
    "django": [], "flask": [], "fastapi": [], "spring boot": ["spring framework"], "laravel": [],
    ".net": ["dotnet", "asp.net"], "bootstrap": [], "tailwind": ["tailwind css"], "streamlit": [],
    "rest api": ["restful", "rest apis", "restful api"], "graphql": [], "flutter": [], "android": [],
    # Data / AI
    "machine learning": ["ml"], "deep learning": ["dl"], "natural language processing": ["nlp"],
    "computer vision": ["image processing"], "data analysis": ["data analytics"],
    "data science": [], "statistics": [], "pandas": [], "numpy": [], "scikit-learn": ["sklearn", "scikit learn"],
    "tensorflow": [], "keras": [], "pytorch": ["torch"], "opencv": [], "nltk": [], "spacy": [],
    "transformers": ["bert", "hugging face", "huggingface"], "llm": ["large language models", "generative ai", "genai"],
    "tesseract": [], "ocr": ["optical character recognition"], "matplotlib": [], "seaborn": [], "plotly": [],
    "power bi": ["powerbi"], "tableau": [], "excel": ["ms excel", "microsoft excel", "advanced excel"],
    "big data": [], "hadoop": [], "spark": ["pyspark", "apache spark"], "etl": [],
    "feature engineering": [], "tf-idf": ["tfidf"], "time series": [],
    # Databases
    "mysql": [], "postgresql": ["postgres"], "sqlite": [], "mongodb": ["mongo"], "oracle": [],
    "redis": [], "sql server": ["mssql"], "firebase": [], "elasticsearch": [],
    # Cloud / DevOps
    "aws": ["amazon web services"], "azure": ["microsoft azure"], "gcp": ["google cloud"],
    "docker": [], "kubernetes": ["k8s"], "jenkins": [], "ci/cd": ["cicd", "continuous integration"],
    "git": ["github", "gitlab"], "linux": ["unix"], "terraform": [], "ansible": [], "nginx": [],
    "microservices": [], "devops": [],
    # Testing / practices
    "unit testing": ["pytest", "junit"], "selenium": [], "agile": ["scrum"], "jira": [],
    "oop": ["object oriented programming", "object-oriented"], "data structures": ["dsa"],
    "algorithms": [], "system design": [],
    # Design / business / soft skills
    "figma": [], "ui/ux": ["ui design", "ux design", "user experience"], "photoshop": [],
    "seo": ["search engine optimization"], "digital marketing": [], "salesforce": [],
    "project management": [], "communication": ["communication skills"], "leadership": ["team leadership"],
    "problem solving": ["problem-solving"], "teamwork": ["team player"], "accounting": [], "tally": [],
    "networking": ["tcp/ip", "computer networks"], "cybersecurity": ["cyber security", "information security"],
}


def all_aliases() -> list[tuple[str, str]]:
    """(alias, canonical) pairs, longest alias first so multi-word terms win."""
    pairs = []
    for canonical, aliases in SKILLS.items():
        pairs.append((canonical, canonical))
        pairs.extend((a, canonical) for a in aliases)
    return sorted(pairs, key=lambda p: len(p[0]), reverse=True)
