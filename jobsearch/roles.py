"""Job titles, role families, and places - used to read a resume and to compare job titles."""
import re

# Role families: keywords that put a job title into a family. Longer, more specific keywords win.
FAMILIES = {
    "devops": ["devops", "dev ops", "sre", "site reliability", "reliability engineer", "platform engineer", "platform engineering",
               "cloud", "infrastructure", "infra", "systems engineer", "system engineer", "systems administrator",
               "system administrator", "sysadmin", "linux administrator", "linux admin", "release engineer", "build engineer",
               "build and release", "kubernetes", "cloudops", "devsecops", "production support", "operations engineer",
               "aws", "azure", "gcp", "middleware", "observability"],
    "data": ["data engineer", "data scientist", "data analyst", "machine learning", "ml engineer", "ai engineer", "analytics",
             "bi developer", "business intelligence", "etl", "big data", "mlops", "data science", "power bi"],
    "qa": ["qa", "quality assurance", "test engineer", "tester", "testing", "sdet", "automation test", "quality engineer"],
    "mobile": ["android", "ios", "mobile", "flutter", "react native"],
    "security": ["security", "soc analyst", "penetration", "cyber", "infosec", "appsec"],
    "network": ["network engineer", "network administrator", "noc engineer", "network"],
    "support": ["support engineer", "technical support", "it support", "helpdesk", "help desk", "desktop support",
                "customer support", "service desk", "application support", "support associate"],
    "management": ["product manager", "project manager", "program manager", "scrum master", "delivery manager", "engineering manager"],
    "design": ["designer", "ux", "ui/ux", "ui ux", "product design"],
    "software": ["software engineer", "software developer", "developer", "programmer", "sde", "backend", "back end", "back-end",
                 "frontend", "front end", "front-end", "full stack", "fullstack", "full-stack", "web developer",
                 "application developer", "java", "python developer", ".net", "node", "react", "angular", "golang"],
    "business": ["business analyst", "consultant", "sales", "marketing", "account manager", "recruiter", "human resources"],
}

ROLE_TITLES = [
    "DevOps Engineer", "Senior DevOps Engineer", "DevSecOps Engineer", "Site Reliability Engineer", "SRE", "Cloud Engineer",
    "Cloud Architect", "Platform Engineer", "Infrastructure Engineer", "Systems Engineer", "System Administrator",
    "Linux Administrator", "Build and Release Engineer", "Release Engineer", "Cloud Operations Engineer", "Kubernetes Engineer",
    "Software Engineer", "Software Developer", "Full Stack Developer", "Full Stack Engineer", "Backend Developer",
    "Backend Engineer", "Frontend Developer", "Frontend Engineer", "Web Developer", "Java Developer", "Python Developer",
    ".NET Developer", "React Developer", "Node.js Developer", "Data Engineer", "Data Scientist", "Data Analyst",
    "Machine Learning Engineer", "ML Engineer", "AI Engineer", "Business Intelligence Analyst", "QA Engineer",
    "Test Engineer", "Automation Test Engineer", "SDET", "Android Developer", "iOS Developer", "Mobile Developer",
    "Flutter Developer", "Security Engineer", "Cyber Security Analyst", "SOC Analyst", "Network Engineer",
    "Network Administrator", "Technical Support Engineer", "Support Engineer", "Application Support Engineer",
    "IT Support Engineer", "Product Manager", "Project Manager", "Program Manager", "Scrum Master", "Business Analyst",
    "UI/UX Designer", "Product Designer", "Solutions Architect",
]

GENERIC = {"engineer", "engineering", "developer", "development", "senior", "sr", "junior", "jr", "lead", "principal", "staff",
           "associate", "specialist", "consultant", "ii", "iii", "iv", "i", "l1", "l2", "l3", "l4", "the", "and", "of", "for",
           "with", "remote", "hybrid", "intern", "trainee", "manager", "analyst", "executive", "officer", "expert", "head",
           "team", "member", "job", "role", "position", "contract", "full", "time", "part", "wfh", "work", "from", "home",
           "india", "immediate", "joiner", "urgent", "hiring", "opening", "a", "an", "in", "at", "to", "on", "or", "new"}

SENIOR_WORDS = re.compile(r"\b(senior|sr\.?|lead|staff)\b", re.I)
VERY_SENIOR_WORDS = re.compile(r"\b(principal|architect|head|director|vp|vice president|manager|chief)\b", re.I)
JUNIOR_WORDS = re.compile(r"\b(junior|jr\.?|intern|internship|fresher|trainee|graduate|entry[- ]level|apprentice)\b", re.I)


def _norm(s):
    return " " + re.sub(r"[^a-z0-9+#./]+", " ", str(s or "").lower()).strip() + " "


def family_of(title):
    t = _norm(title)
    best, best_len = None, 0
    for fam, words in FAMILIES.items():
        score = sum(len(w) for w in words if f" {w} " in t or (len(w) > 4 and w in t))
        if score > best_len:
            best, best_len = fam, score
    return best


def core_words(role):
    return [w for w in _norm(role).split() if w not in GENERIC and len(w) > 1]


def title_score(job_title, targets, target_family, my_skills=()):
    """How close a job title is to the roles you want:
    1.0 the role itself, 0.9 its core word (devops), 0.75 same family (site reliability, cloud...),
    0.5 names a tool you know (AWS Support Engineer), else 0."""
    t = _norm(job_title)
    if not t.strip():
        return 0.0
    for role in targets:
        if _norm(role).strip() and _norm(role) in t:
            return 1.0
    cores = {w for r in targets for w in core_words(r)}
    words = set(t.split())
    if cores & words or any(len(c) > 4 and c in t for c in cores):
        return 0.9
    fam_words = FAMILIES.get(target_family) or []
    if any(f" {w} " in t for w in fam_words) or family_of(job_title) == target_family:
        return 0.75
    if my_skills:
        from .skills import find_in_text
        if set(find_in_text(job_title)) & set(my_skills):
            return 0.5
    return 0.0


def detect_title(text):
    """Best role title from a resume: the headline first, then the summary."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    pools = ["\n".join(lines[:6]), "\n".join(lines[:40])]
    for pool in pools:
        low = pool.lower()
        hits = [(low.find(r.lower()), -len(r), r) for r in ROLE_TITLES if re.search(rf"(?<![a-z]){re.escape(r.lower())}(?![a-z])", low)]
        if hits:
            hits.sort()
            return hits[0][2]
    m = re.search(r"\b((?:[A-Z][\w/+.#-]*\s){0,3}(?:Engineer|Developer|Analyst|Scientist|Manager|Architect|Administrator|Designer|Consultant|Specialist))\b",
                  "\n".join(lines[:10]))
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------- places
CITIES = {
    # India
    "Hyderabad": "India", "Secunderabad": "India", "Bengaluru": "India", "Bangalore": "India", "Pune": "India", "Chennai": "India",
    "Mumbai": "India", "Navi Mumbai": "India", "Thane": "India", "Delhi": "India", "New Delhi": "India", "Noida": "India",
    "Gurgaon": "India", "Gurugram": "India", "Kolkata": "India", "Ahmedabad": "India", "Jaipur": "India", "Indore": "India",
    "Chandigarh": "India", "Coimbatore": "India", "Kochi": "India", "Trivandrum": "India", "Thiruvananthapuram": "India",
    "Visakhapatnam": "India", "Vijayawada": "India", "Mysore": "India", "Mysuru": "India", "Nagpur": "India", "Bhubaneswar": "India",
    "Lucknow": "India", "Vadodara": "India", "Surat": "India", "Mohali": "India", "Warangal": "India", "Madurai": "India",
    # Elsewhere
    "London": "United Kingdom", "Manchester": "United Kingdom", "Dublin": "Ireland", "Berlin": "Germany", "Munich": "Germany",
    "Amsterdam": "Netherlands", "Paris": "France", "Madrid": "Spain", "Barcelona": "Spain", "Lisbon": "Portugal",
    "Warsaw": "Poland", "Zurich": "Switzerland", "Stockholm": "Sweden", "Dubai": "United Arab Emirates",
    "Abu Dhabi": "United Arab Emirates", "Riyadh": "Saudi Arabia", "Doha": "Qatar", "Singapore": "Singapore",
    "Kuala Lumpur": "Malaysia", "Sydney": "Australia", "Melbourne": "Australia", "Toronto": "Canada", "Vancouver": "Canada",
    "New York": "United States", "San Francisco": "United States", "Seattle": "United States", "Austin": "United States",
    "Chicago": "United States", "Boston": "United States", "Los Angeles": "United States", "Dallas": "United States",
}
ALIASES = {"bangalore": "Bengaluru", "gurgaon": "Gurugram", "new delhi": "Delhi", "mysore": "Mysuru",
           "thiruvananthapuram": "Trivandrum", "secunderabad": "Hyderabad", "navi mumbai": "Mumbai", "bombay": "Mumbai",
           "madras": "Chennai", "calcutta": "Kolkata", "greater hyderabad area": "Hyderabad", "greater bengaluru area": "Bengaluru"}
COUNTRIES = ["India", "United States", "USA", "United Kingdom", "UK", "Canada", "Germany", "Netherlands", "Ireland", "France",
             "Spain", "Portugal", "Poland", "Switzerland", "Sweden", "United Arab Emirates", "UAE", "Saudi Arabia", "Qatar",
             "Singapore", "Malaysia", "Australia", "New Zealand", "Philippines", "Indonesia", "Japan", "Brazil", "Mexico"]


def canonical_city(name):
    n = str(name or "").strip()
    if not n:
        return ""
    low = n.lower()
    if low in ALIASES:
        return ALIASES[low]
    for c in CITIES:
        if c.lower() == low:
            return ALIASES.get(low, c)
    return n


def find_place(text):
    """(city, country) from a resume header or a job location string."""
    s = str(text or "")
    city = country = ""
    best = None
    for c in sorted(CITIES, key=len, reverse=True):
        m = re.search(rf"(?<![A-Za-z]){re.escape(c)}(?![A-Za-z])", s, re.I)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), c)
    if best:
        city = canonical_city(best[1])
        country = CITIES.get(best[1], "")
    for c in COUNTRIES:
        if re.search(rf"(?<![A-Za-z]){re.escape(c)}(?![A-Za-z])", s):
            country = {"USA": "United States", "UK": "United Kingdom", "UAE": "United Arab Emirates"}.get(c, c)
            break
    return city, country


def same_city(a, b):
    return bool(a and b) and canonical_city(a).lower() == canonical_city(b).lower()


def is_country(s):
    return str(s or "").strip().lower() in {c.lower() for c in COUNTRIES} | {"worldwide", "anywhere", "remote"}
