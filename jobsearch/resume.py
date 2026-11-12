"""Read a resume (PDF, DOCX, TXT, MD) and work out what to search for and how to score jobs.

Everything detected here can be overridden in config.json ("profile" section)."""
import re
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from . import roles, skills


@dataclass
class Profile:
    name: str = ""
    title: str = ""
    family: str = ""
    skills: list = field(default_factory=list)
    years_total: float | None = None
    years_relevant: float | None = None
    city: str = ""
    country: str = ""
    resume_file: str = ""

    def to_dict(self):
        return asdict(self)


class ResumeError(Exception):
    pass


# ---------------------------------------------------------------- text extraction
def read_text(path):
    p = Path(path).expanduser()
    if not p.is_file():
        raise ResumeError(f"Resume not found: {p}")
    ext = p.suffix.lower()
    if ext == ".pdf":
        text = _pdf_text(p)
    elif ext == ".docx":
        text = _docx_text(p)
    elif ext in (".txt", ".md", ".text"):
        text = p.read_text(encoding="utf-8", errors="replace")
    else:
        raise ResumeError(f"Unsupported resume type '{ext}'. Use PDF, DOCX, TXT or MD.")
    text = re.sub(r"[ \t ​  ]+", " ", text)  # PDF extractors pad words with odd spaces
    return "\n".join(line.strip() for line in text.splitlines())


def _pdf_text(p):
    errors = []
    try:
        try:
            import pymupdf as fitz  # PyMuPDF keeps the layout best; optional
        except ImportError:
            import fitz  # older PyMuPDF releases
        with fitz.open(str(p)) as doc:
            text = "\n".join(page.get_text() for page in doc)
        if text.strip():
            return text
    except ImportError:
        errors.append("PyMuPDF not installed")
    except Exception as e:  # damaged or unusual PDFs: try the other reader
        errors.append(f"PyMuPDF: {e}")
    try:
        from pypdf import PdfReader
        text = "\n".join((page.extract_text() or "") for page in PdfReader(str(p)).pages)
        if text.strip():
            return text
    except ImportError:
        errors.append("pypdf not installed")
    except Exception as e:
        errors.append(f"pypdf: {e}")
    hint = " Run: pip install pypdf" if any("not installed" in e for e in errors) else ""
    raise ResumeError(f"Couldn't read text from {p.name} ({'; '.join(errors) or 'no text layer, is it a scanned image?'}).{hint}")


def _docx_text(p):
    try:
        with zipfile.ZipFile(p) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    except (KeyError, zipfile.BadZipFile) as e:
        raise ResumeError(f"Couldn't read {p.name}: {e}")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    import html
    return html.unescape(xml)


# ---------------------------------------------------------------- detection
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_POINT = rf"(?:{_MON}\s*,?\s*\d{{4}}|\d{{1,2}}[/-]\d{{4}}|\d{{4}})"
_RANGE = re.compile(rf"({_POINT})\s*(?:-|–|—|to|till|until)\s*({_POINT}|present|current|now|till date|date)", re.I)
_SECTION = re.compile(r"^\s*(work experience|professional experience|experience|employment history|employment|career history|"
                      r"education|academic|projects?|certifications?|skills|technical skills|summary|profile|achievements|awards)\s*:?\s*$",
                      re.I | re.M)
_EDU = re.compile(r"\b(b\.?\s?tech|b\.?e\.?|bachelor|master|m\.?\s?tech|mba|university|college|school|degree|diploma|cgpa|gpa)\b", re.I)


def _point(s, end=False):
    s = s.strip().lower()
    if s in ("present", "current", "now", "till date", "date"):
        t = date.today()
        return t.year + (t.month - 1) / 12
    m = re.match(rf"({_MON})\s*,?\s*(\d{{4}})", s)
    if m:
        return int(m.group(2)) + (MONTHS[m.group(1)[:3]] - 1) / 12
    m = re.match(r"(\d{1,2})[/-](\d{4})", s)
    if m:
        return int(m.group(2)) + (int(m.group(1)) - 1) / 12
    return int(s[:4]) + (11 / 12 if end else 0)


def _experience_block(text):
    """Text of the work-experience section, or the whole text when there are no headings."""
    heads = [(m.start(), m.group(1).lower()) for m in _SECTION.finditer(text)]
    for i, (pos, name) in enumerate(heads):
        if "experience" in name or "employment" in name or "career" in name:
            end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
            return text[pos:end]
    return text


def years_from_dates(text, family):
    """(total, relevant) years from date ranges such as 'Jul 2023 - Present', merging overlaps."""
    block = _experience_block(text)
    lines = block.splitlines()
    spans, relevant = [], []
    for i, line in enumerate(lines):
        for m in _RANGE.finditer(line):
            context = f"{lines[i - 1] if i else ''} {line[:m.start()]}"
            if _EDU.search(context):
                continue
            try:
                a, b = _point(m.group(1)), _point(m.group(2), end=True)
            except (ValueError, KeyError):
                continue
            if not (1970 < a <= b + 0.01 < 2100) or b - a > 45:
                continue
            spans.append((a, b))
            if family and roles.family_of(context) == family:
                relevant.append((a, b))

    def merged(xs):
        total, cur = 0.0, None
        for a, b in sorted(xs):
            if cur and a <= cur[1]:
                cur[1] = max(cur[1], b)
            else:
                if cur:
                    total += cur[1] - cur[0]
                cur = [a, b]
        if cur:
            total += cur[1] - cur[0]
        return round(total, 1) if xs else None

    return merged(spans), merged(relevant)


def years_stated(text, family, title):
    """(total, relevant) from sentences like '5 years of overall IT experience, including 3+ years of DevOps'."""
    head = text[:3000]
    total = relevant = None
    title_words = set(roles.core_words(title)) | set((roles.FAMILIES.get(family) or [])[:12])
    for m in re.finditer(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)\b", head, re.I):
        n = float(m.group(1))
        if n > 40:
            continue
        after = head[m.end(): m.end() + 70]
        after = re.split(r"\d", after, maxsplit=1)[0].lower()
        if not re.search(r"experience|expertise|exp\b|industry|it\b|working|hands-on|professional", after + head[max(0, m.start() - 40): m.start()].lower()):
            continue
        total = n if total is None else max(total, n)
        if any(w and re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", after) for w in title_words):
            relevant = n if relevant is None else min(relevant, n)
    if relevant is not None and total is not None and relevant > total:
        total = relevant
    return total, relevant


def detect_name(text):
    for line in (l.strip() for l in text.splitlines()):
        if not line:
            continue
        if 1 < len(line.split()) <= 4 and re.fullmatch(r"[A-Za-z][A-Za-z .'-]+", line) and len(line) < 40:
            return line.title() if line.isupper() else line
        break
    return ""


def skills_section(text):
    m = re.search(r"(?im)^\s*(technical skills|skills|core competencies|key skills|tech stack|tools)\s*:?\s*$", text)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = _SECTION.search(rest)
    return rest[: nxt.start()] if nxt else rest[:2500]


def build_profile(path, overrides=None):
    """Read the resume and return a Profile. `overrides` (from config) win over what was detected."""
    text = read_text(path)
    o = {k: v for k, v in (overrides or {}).items() if v not in (None, "", [])}
    title = o.get("title") or roles.detect_title(text)
    family = o.get("family") or roles.family_of(title) or "software"
    found = skills.find_in_text(text)
    found += skills.find_in_text(skills_section(text), tag_context=True)
    found += skills.from_tags(o.get("extra_skills", []))
    drop = {s.lower() for s in o.get("ignore_skills", [])}
    found = [s for s in skills.expand(list(dict.fromkeys(found))) if s.lower() not in drop]

    stated_total, stated_rel = years_stated(text, family, title)
    dated_total, dated_rel = years_from_dates(text, family)
    total = o.get("years_total") or stated_total or dated_total
    relevant = o.get("years_relevant") or stated_rel or dated_rel or total
    header = "\n".join(text.splitlines()[:12])
    city, country = roles.find_place(header)
    if not city:
        city, country2 = roles.find_place(text[:4000])
        country = country or country2
    return Profile(
        name=o.get("name") or detect_name(text),
        title=title,
        family=family,
        skills=found,
        years_total=float(total) if total is not None else None,
        years_relevant=float(relevant) if relevant is not None else None,
        city=roles.canonical_city(o.get("city") or city),
        country=o.get("country") or country,
        resume_file=str(Path(path).name),
    )
