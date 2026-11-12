"""Small parsers shared by every source: dates, experience ranges, applicant counts, HTML, URLs."""
import html
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

UTC = timezone.utc
DASH = "–"


def now():
    return datetime.now(UTC)


def text(value, limit=None):
    """Plain text from a string that may contain HTML."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = ", ".join(text(v) for v in value if v)
    s = str(value)
    if "<" in s and ">" in s:
        s = re.sub(r"(?i)<\s*(br|/p|/li|/div|/h\d)\s*/?>", "\n", s)
        s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v ​]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s).strip()
    return s[:limit] if limit else s


def first(*values):
    """The first value that isn't empty."""
    for v in values:
        if v not in (None, "", [], {}):
            return v
    return None


def dig(obj, path, default=None):
    """dig(item, 'companyDetail.name')"""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return default
    return default if cur is None else cur


# ---------------------------------------------------------------- dates
_REL = re.compile(r"(\d+)\+?\s*(minute|min|hour|hr|day|week|month|year)s?\b", re.I)


def parse_date(value, naive_utc_offset_hours=0.0):
    """ISO strings, 'YYYY-MM-DD HH:MM:SS', epoch seconds/ms, or 'Posted 3 hours ago' -> (datetime UTC, has_time).

    naive_utc_offset_hours: the timezone of timestamps that carry none (Naukri's are India time, 5.5).
    Returns (None, False) when nothing parses."""
    if value in (None, ""):
        return None, False
    if isinstance(value, (int, float)) and value > 0:
        ts = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(ts, UTC), True
    s = str(value).strip()
    if re.fullmatch(r"\d{10,13}", s):
        return parse_date(int(s))
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}(?::\d{2})?)(\.\d+)?)?\s*(Z|[+-]\d{2}:?\d{2})?", s)
    if m:
        day, clock, _, tz = m.groups()
        if not clock:
            return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC), False
        fmt = "%Y-%m-%d %H:%M:%S" if clock.count(":") == 2 else "%Y-%m-%d %H:%M"
        dt = datetime.strptime(f"{day} {clock}", fmt)
        if tz and tz != "Z":
            sign = 1 if tz[0] == "+" else -1
            hh, mm = int(tz[1:3]), int(tz[-2:])
            dt = dt - sign * timedelta(hours=hh, minutes=mm)
        elif not tz:
            dt = dt - timedelta(hours=naive_utc_offset_hours)
        return dt.replace(tzinfo=UTC), True
    low = s.lower()
    if any(w in low for w in ("just now", "just posted", "few hours", "today", "few minutes", "moments ago")):
        return now(), True
    if "yesterday" in low:
        return now() - timedelta(days=1), False
    m = _REL.search(low)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"minute": timedelta(minutes=n), "min": timedelta(minutes=n), "hour": timedelta(hours=n), "hr": timedelta(hours=n),
                 "day": timedelta(days=n), "week": timedelta(weeks=n), "month": timedelta(days=30 * n), "year": timedelta(days=365 * n)}[unit]
        return now() - delta, unit in ("minute", "min", "hour", "hr")
    for fmt in ("%d %b %Y", "%b %d, %Y", "%d %B %Y", "%B %d, %Y", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.strptime(s, fmt)
            return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC), "%H" in fmt
        except ValueError:
            pass
    return None, False


def posted_label(dt, has_time):
    """'3h ago' for today's jobs with a known time, otherwise '9 Nov'."""
    if not dt:
        return ""
    age = now() - dt
    if has_time and timedelta(0) <= age < timedelta(hours=1):
        return f"{max(1, int(age.total_seconds() // 60))}m ago"
    if has_time and timedelta(0) <= age < timedelta(hours=24):
        return f"{int(age.total_seconds() // 3600)}h ago"
    return f"{dt.day} {dt:%b}"


def within(dt, has_time, hours):
    """Was it posted inside the window? Date-only values get the benefit of the doubt for that day."""
    if dt is None:
        return True  # unknown: keep, the source's own filter already applied
    limit = now() - timedelta(hours=hours)
    if not has_time:
        limit = limit.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt >= limit


# ---------------------------------------------------------------- experience
def parse_years(value):
    """'3-5 Yrs', '5+ years', '4–8 yrs', 'At least 5 years', '0 to 1 Years', {'min':5} -> (min, max)."""
    if value in (None, ""):
        return None, None
    if isinstance(value, dict):
        lo, hi = value.get("min"), value.get("max")
        if lo is None and hi is None:
            return parse_years(value.get("text"))
        return _num(lo), _num(hi)
    if isinstance(value, (int, float)):
        return float(value), None
    s = str(value).lower().replace(DASH, "-").replace("—", "-")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:yrs?|years?)?", s)
    if m and ("yr" in s or "year" in s or re.fullmatch(r"\s*\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*", s)):
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:yrs?|years?)", s)
    if m:
        return float(m.group(1)), None
    if re.fullmatch(r"\s*\d+(?:\.\d+)?\s*\+?\s*", s):
        return float(re.sub(r"[^\d.]", "", s)), None
    if any(w in s for w in ("fresher", "entry level", "no experience")):
        return 0.0, 1.0
    return None, None


def _num(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def years_label(lo, hi):
    if lo is None and hi is None:
        return ""
    f = lambda x: str(int(x)) if float(x).is_integer() else f"{x:g}"
    if lo is not None and hi is not None and hi > lo:
        return f"{f(lo)}{DASH}{f(hi)} yrs"
    if lo is not None:
        return f"{f(lo)}+ yrs"
    return f"Up to {f(hi)} yrs"


def years_in_text(description):
    """Find 'X+ years' requirements in a job description; returns (min, max) of the main one."""
    if not description:
        return None, None
    s = description.lower().replace(DASH, "-")
    best = None
    for m in re.finditer(r"(\d{1,2})\s*(?:\+|plus)?\s*(?:-|to)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+\w+){0,4}?\s+(?:experience|exp\b)", s):
        lo, hi = float(m.group(1)), float(m.group(2)) if m.group(2) else None
        if lo > 25 or (hi is not None and hi < lo):
            continue
        if best is None or lo > best[0]:
            best = (lo, hi)
    return best or (None, None)


# ---------------------------------------------------------------- applicants
def applicants_label(value):
    """'145', '200+', 'Under 25' or ''."""
    if value in (None, ""):
        return ""
    if isinstance(value, dict):
        lo, hi, t = value.get("min"), value.get("max"), str(value.get("text") or "")
        if re.search(r"first|be among|under|fewer", t, re.I):
            n = re.search(r"\d+", t)
            return f"Under {n.group()}" if n else "Under 25"
        if lo is not None and hi is None and re.search(r"over|more than|\+", t, re.I):
            return f"{int(lo)}+"
        if lo is not None:
            return str(int(lo))
        return applicants_label(t)
    if isinstance(value, (int, float)):
        return str(int(value))
    s = str(value)
    m = re.search(r"(\d[\d,]*)", s)
    if re.search(r"first|be among|under|fewer|less than", s, re.I):
        return f"Under {m.group(1)}" if m else "Under 25"
    if m and re.search(r"over|more than|\+", s, re.I):
        return f"{m.group(1).replace(',', '')}+"
    return m.group(1).replace(",", "") if m else ""


def applicants_count(label):
    """Rough number for scoring."""
    if not label:
        return None
    m = re.search(r"\d+", label)
    if not m:
        return None
    n = int(m.group())
    return max(1, n // 2) if label.lower().startswith("under") else n


# ---------------------------------------------------------------- money
def money(lo, hi=None, currency="", period="", raw=""):
    if raw and not re.fullmatch(r"\s*(not disclosed|unspecified|n/?a|none|-)\s*", str(raw), re.I):
        return str(raw).replace(".00", "").replace(" - ", f" {DASH} ").strip()
    if lo in (None, "", 0) and hi in (None, "", 0):
        return ""
    sym = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}.get(str(currency).upper(), f"{currency} " if currency else "")
    per = {"year": "/yr", "yearly": "/yr", "annual": "/yr", "month": "/mo", "monthly": "/mo", "hour": "/hr", "hourly": "/hr"}.get(str(period).lower(), "")

    def f(x):
        try:
            x = float(x)
        except (TypeError, ValueError):
            return str(x)
        if sym == "₹" and x >= 100000:
            return f"{x / 100000:.1f}".rstrip("0").rstrip(".") + "L"
        if x >= 1000:
            return f"{x / 1000:.0f}k"
        return f"{x:g}"

    if lo not in (None, "", 0) and hi not in (None, "", 0) and hi != lo:
        return f"{sym}{f(lo)} {DASH} {sym}{f(hi)}{per}"
    return f"{sym}{f(lo or hi)}{per}"


# ---------------------------------------------------------------- urls
def clean_url(url):
    """Drop utm_* tracking; keep everything the site needs."""
    if not url or not str(url).startswith("http"):
        return ""
    parts = urlsplit(str(url))
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    return urlunsplit(parts._replace(query=urlencode(query)))


def host(url):
    try:
        return urlsplit(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def off_site(url, *board_hosts):
    """True when url points somewhere other than the job board itself (a company careers page)."""
    h = host(url)
    return bool(h) and not any(b in h for b in board_hosts)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")


def norm_key(s):
    s = re.sub(r"\(.*?\)", " ", str(s or "").lower())
    s = re.sub(r"\b(pvt|private|ltd|limited|inc|llc|llp|technologies|technology|solutions|services|india|the)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)
