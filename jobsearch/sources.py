"""One adapter per Apify actor: how to ask it for jobs, and how to read what it returns.

Each adapter turns the shared Search (roles, place, freshness, limit) into the actor's own input,
using the actor's server-side filters so you only pay for fresh, relevant rows, and turns each
result row into the common job shape used by scoring and the report.

Prices are the free-plan prices per event (paid plans are cheaper); they are only used for the
estimate shown before a run, and as the per-run spending cap passed to Apify.
"""
import math
import re
from dataclasses import dataclass
from urllib.parse import urlencode

from . import normalize as nz
from . import roles, skills


@dataclass
class Search:
    roles: list
    location: str = ""      # what to type in the location box ("India", "Hyderabad")
    city: str = ""          # canonical city when the location is a city
    country: str = ""
    hours: int = 24         # only jobs posted within this many hours
    limit: int = 25         # max jobs per source (what you pay for)
    years: float | None = None
    remote: bool = False    # remote-only where the board supports it
    only_new: bool = False  # actor-side "only new since my last run" where supported
    family: str = ""

    @property
    def days(self):
        return max(1, math.ceil(self.hours / 24))

    @property
    def place(self):
        """City if we have one, else the location text unless it's a whole country."""
        if self.city:
            return self.city
        return "" if roles.is_country(self.location) else self.location

    def core_words(self):
        words = [w for r in self.roles for w in roles.core_words(r)]
        return list(dict.fromkeys(words)) or [r.lower() for r in self.roles]


def _pick(options, need):
    """Smallest allowed value that covers `need` (e.g. freshness days 1/3/7/15/30)."""
    for o in options:
        if o >= need:
            return o
    return options[-1]


class Source:
    key = ""
    label = ""
    actor = ""
    site = ()                # job-board hosts: links elsewhere are the company's own site
    start_usd = 0.0
    item_usd = 0.0
    min_items = 0
    default = False
    region = "Global"
    blurb = ""
    stale_risk = False      # True when the actor has no date filter, so older jobs are billed too
    actor_id = ""

    def items_cap(self, s):
        return max(self.min_items, s.limit)

    def estimate(self, s):
        return self.start_usd + self.item_usd * self.items_cap(s)

    def build_input(self, s):
        raise NotImplementedError

    def normalize(self, it, s):
        raise NotImplementedError

    # helper that every normalizer ends with
    def job(self, it, *, id, title, company, url, location="", remote=None, posted=None, posted_tz=0.0,
            applicants=None, exp=None, salary="", apply_url="", easy=False, kind=None, note="",
            tags=(), description="", employment_type="", label=None):
        title = nz.text(title)
        url = nz.clean_url(url) or nz.clean_url(apply_url)
        if not title or not url:
            return None
        lo, hi = (nz._num(exp[0]), nz._num(exp[1])) if isinstance(exp, tuple) else nz.parse_years(exp)
        dt, has_time = nz.parse_date(posted, posted_tz) if not isinstance(posted, tuple) else posted
        link = nz.clean_url(apply_url)
        if kind is None:
            if link and nz.off_site(link, *self.site):
                kind = "company"
            elif easy:
                kind, link = "easy", ""
            else:
                kind, link = "board", ""
        elif kind != "company" or not nz.off_site(link, *self.site):
            link = ""
        loc = nz.text(location)
        return {
            "id": f"{self.key}:{id or url}",
            "source": self.key,
            "source_label": label or self.label,
            "title": title,
            "company": nz.text(company) or "Company not shown",
            "location": loc,
            "remote": bool(remote) if remote is not None else bool(re.search(r"\b(remote|work from home|wfh)\b", loc, re.I)) or None,
            "posted_at": dt.isoformat() if dt else "",
            "posted_has_time": has_time,
            "posted": nz.posted_label(dt, has_time),
            "applicants": nz.applicants_label(applicants),
            "exp_min": lo,
            "exp_max": hi,
            "experience": nz.years_label(lo, hi),
            "salary": nz.text(salary),
            "url": url,
            "kind": kind,
            "link": link,
            "note": note,
            "skills": skills.from_tags(tags),
            "description": nz.text(description, 6000),
            "employment_type": nz.text(employment_type),
        }


# ====================================================================== LinkedIn
class LinkedIn(Source):
    key, label, actor = "linkedin", "LinkedIn", "crawlworks/linkedin-jobs-scraper"
    site = ("linkedin.com",)
    start_usd, item_usd = 0.00005, 0.005
    default = True
    blurb = "LinkedIn jobs with applicant counts, Easy Apply vs company-site link, skills."

    @staticmethod
    def _seconds(hours):
        return _pick([86400, 259200, 604800, 2592000], hours * 3600)

    def build_input(self, s):
        secs = self._seconds(s.hours)
        if len(s.roles) <= 1:
            inp = {"query": s.roles[0] if s.roles else "", "location": s.location or "", "timePostedRange": str(secs),
                   "jobsToFetch": s.limit, "onSite": not s.remote, "hybrid": not s.remote, "remote": True,
                   "enrichCompanyDetails": False}
            return inp
        per = max(1, math.ceil(s.limit / len(s.roles)))
        urls = []
        for r in s.roles:
            q = {"keywords": r, "location": s.location or "", "f_TPR": f"r{secs}"}
            if s.remote:
                q["f_WT"] = "2"
            urls.append("https://www.linkedin.com/jobs/search/?" + urlencode(q))
        return {"searchUrls": urls, "jobsToFetch": per, "enrichCompanyDetails": False}

    def normalize(self, it, s):
        app = str(it.get("applicationType") or "")
        easy = "easy" in app.lower()
        apply = it.get("applyUrl") or ""
        kind = note = None
        if not easy and not nz.off_site(apply, *self.site):
            kind, note = "company", "Opens the company site from LinkedIn"
        posted = it.get("postedTime") if re.search(r"minute|hour|just", str(it.get("postedTime") or ""), re.I) else nz.first(it.get("postedDate"), it.get("postedTime"))
        sal = it.get("salary")
        if isinstance(sal, dict):
            sal = sal.get("text") or nz.money(sal.get("min"), sal.get("max"), sal.get("currency", ""), sal.get("period", ""))
        return self.job(it, id=nz.first(it.get("jobId"), it.get("id")), title=it.get("jobTitle") or it.get("title"),
                        company=it.get("companyName"), url=it.get("jobUrl"), location=it.get("location"),
                        posted=posted, applicants=it.get("applicantsCount"), exp=it.get("experienceYears"),
                        salary=sal or "", apply_url=apply, easy=easy, kind=kind, note=note or "",
                        tags=it.get("skills") or [], description=it.get("jobDescription"),
                        employment_type=it.get("employmentType"))


# ====================================================================== Naukri x3
NAUKRI = ("naukri.com", "naukrigulf.com")


class Naukri(Source):
    key, label, actor = "naukri", "Naukri", "blackfalcondata/naukri-jobs-feed"
    site = NAUKRI
    start_usd, item_usd = 0.001, 0.00039
    default = True
    region = "India"
    blurb = "Cheapest Naukri feed ($0.39/1k). Full details, skills, company apply link."

    def build_input(self, s):
        inp = {"sortBy": "date", "freshness": _pick([1, 3, 7, 15, 30], s.days), "maxResults": s.limit,
               "fetchDetails": True, "descriptionFormat": "text", "descriptionMaxLength": 5000}
        if len(s.roles) > 1:
            inp["searchQueries"] = s.roles
        else:
            inp["keyword"] = s.roles[0] if s.roles else ""
        if s.place:
            inp["location"] = s.place
        if s.years is not None:
            inp["experience"] = str(int(s.years))
        if s.remote:
            inp["workMode"] = "remote"
        if s.only_new:
            inp["incremental"] = True
        return inp

    def normalize(self, it, s):
        # applyRedirectUrl is the employer's own page; companyApplyUrl is usually a Naukri endpoint
        apply = nz.first(it.get("applyRedirectUrl"), it.get("companyApplyUrl")) or ""
        salary = nz.money(None, raw=it.get("salary") or "")
        if not salary and not it.get("salaryHidden"):
            salary = nz.money(it.get("salaryMin"), it.get("salaryMax"), it.get("salaryCurrency") or "INR", "year")
        return self.job(it, id=it.get("jobId"), title=it.get("title"), company=it.get("companyName"),
                        url=nz.first(it.get("portalUrl"), it.get("staticUrl"), it.get("jdURL"), it.get("url")), location=it.get("location"),
                        posted=it.get("createdDate"), posted_tz=5.5, applicants=it.get("applyCount"),
                        exp=(it.get("minimumExperience"), it.get("maximumExperience")) if it.get("minimumExperience") is not None else it.get("experienceText"),
                        salary=salary, apply_url=apply, easy=True, tags=it.get("skills") or it.get("keySkills") or [],
                        description=nz.first(it.get("description"), it.get("descriptionMarkdown")),
                        employment_type=it.get("employmentType"))


class NaukriMemo(Source):
    key, label, actor = "naukri-memo23", "Naukri", "memo23/naukri-scraper"
    site = NAUKRI
    start_usd, item_usd = 0.001, 0.0008
    region = "India"
    blurb = "Naukri with the employer's own apply link (applyRedirectUrl) and applicant count."

    def build_input(self, s):
        inp = {"sortBy": "date", "maximumJobs": s.limit, "freshnessDays": s.days,
               "timeFilter": "24h" if s.hours <= 24 else "7d" if s.hours <= 168 else "30d" if s.hours <= 720 else "90d",
               "includeDescription": True, "cleanHtml": True, "descriptionMaxLength": 5000}
        if len(s.roles) > 1:
            inp["searchQueries"] = s.roles
        else:
            inp["searchQuery"] = s.roles[0] if s.roles else ""
        if s.place:
            inp["location"] = s.place.lower()
        if s.years is not None:
            inp["experienceLevel"] = int(s.years)
        if s.remote:
            inp["workMode"] = "2"
        if s.only_new:
            inp["incrementalMode"] = True
        return inp

    def normalize(self, it, s):
        locs = it.get("locations") or []
        loc = ", ".join(l.get("label", "") for l in locs if isinstance(l, dict)) or it.get("location") or ""
        sd = it.get("salaryDetail") or {}
        salary = "" if sd.get("hideSalary") else nz.money(sd.get("minimumSalary"), sd.get("maximumSalary"), sd.get("currency", "INR"), "year")
        ks = it.get("keySkills") or {}
        tags = [x.get("label") for k in ("preferred", "other") for x in (ks.get(k) or []) if isinstance(x, dict)] if isinstance(ks, dict) else ks
        company = nz.dig(it, "companyDetail.name") or it.get("companyName") or \
            re.sub(r"-jobs-careers-\d+$", "", str(it.get("staticCompanyName") or "")).replace("-", " ").title()
        return self.job(it, id=it.get("jobId"), title=it.get("title"), company=company,
                        url=nz.first(it.get("staticUrl"), it.get("url"), it.get("jdURL")), location=loc,
                        remote=str(it.get("wfhType")) == "2" or None, posted=it.get("createdDate"), posted_tz=5.5,
                        applicants=it.get("applyCount"),
                        exp=(it.get("minimumExperience"), it.get("maximumExperience")) if it.get("minimumExperience") is not None else it.get("experienceText"),
                        salary=salary, apply_url=it.get("applyRedirectUrl") or "", easy=True, tags=tags or [],
                        description=nz.first(it.get("description"), it.get("shortDescription")),
                        employment_type=it.get("employmentType"))


class NaukriMK(Source):
    key, label, actor = "naukri-mk", "Naukri", "muhammetakkurtt/naukri-job-scraper"
    site = NAUKRI
    start_usd, item_usd = 0.001, 0.0015
    region = "India"
    blurb = "Naukri search results (basic rows; one role per run)."

    def build_input(self, s):
        role = s.roles[0] if s.roles else ""
        fresh = str(_pick([1, 3, 7, 15, 30], s.days))
        inp = {"jobBoard": "naukri", "keyword": role, "maxJobs": s.limit, "sortBy": "date", "freshness": fresh,
               "fetchDetails": False}
        if s.years is not None:
            inp["experience"] = str(min(13, int(s.years)))
        if s.place:
            q = {"k": role, "l": s.place, "jobAge": fresh}
            if s.years is not None:
                q["experience"] = str(int(s.years))
            inp["searchUrl"] = f"https://www.naukri.com/{nz.slug(role)}-jobs-in-{nz.slug(s.place)}?{urlencode(q)}"
        if s.remote:
            inp["workMode"] = ["remote"]
        return inp

    def normalize(self, it, s):
        posted = nz.first(it.get("createdDate"), it.get("footerPlaceholderLabel"))
        sd = it.get("salaryDetail") or {}
        salary = it.get("salary") if it.get("salary") and "not disclosed" not in str(it.get("salary")).lower() else \
            ("" if sd.get("hideSalary") else nz.money(sd.get("minimumSalary"), sd.get("maximumSalary"), sd.get("currency", "INR"), "year"))
        return self.job(it, id=it.get("jobId"), title=it.get("title"), company=it.get("companyName"),
                        url=nz.first(it.get("jdURL"), it.get("url")), location=it.get("location"),
                        posted=posted, posted_tz=5.5, applicants=it.get("applyCount"),
                        exp=(it.get("minimumExperience"), it.get("maximumExperience")) if it.get("minimumExperience") not in (None, "") else nz.first(it.get("experienceText"), it.get("experience")),
                        salary=salary or "", easy=True,
                        tags=[t for t in str(it.get("tagsAndSkills") or "").split(",") if t.strip()],
                        description=it.get("jobDescription"))


# ====================================================================== India boards
class Instahyre(Source):
    key, label, actor = "instahyre", "Instahyre", "getascraper/instahyre-jobs-scraper"
    site = ("instahyre.com",)
    start_usd, item_usd = 0.00005, 0.00105
    region = "India"
    blurb = "Instahyre tech jobs by keyword, skills and city (no posting dates)."

    def build_input(self, s):
        inp = {"jobFunctionSlugs": [], "keywords": s.core_words(), "keywordMatch": "any", "maxItems": s.limit,
               "maxPages": 5, "includeDetails": False, "remoteOnly": s.remote}
        if s.place:
            inp["locations"] = [s.place]
        if s.only_new:
            inp.update(monitorMode="changes_only", stateName=f"jobsearch-{nz.slug('-'.join(s.roles))}")
        return inp

    def normalize(self, it, s):
        locs = it.get("locations")
        loc = ", ".join(locs) if isinstance(locs, list) else nz.first(it.get("locationsRaw"), locs, "")
        return self.job(it, id=it.get("jobId"), title=it.get("title") or it.get("candidateTitle"),
                        company=it.get("companyName"), url=nz.first(it.get("publicUrl"), it.get("jobUrl")), location=loc,
                        remote=it.get("isRemote"), exp=(it.get("experienceMin"), it.get("experienceMax")) if it.get("experienceMin") is not None else None,
                        easy=True, tags=it.get("skills") or [], description=it.get("description"),
                        employment_type=it.get("jobType"))


class InstahyreMemo(Source):
    key, label, actor = "instahyre-memo23", "Instahyre", "memo23/instahyre-jobs-scraper"
    site = ("instahyre.com",)
    start_usd, item_usd = 0.0001, 0.0015
    region = "India"
    blurb = "Instahyre with apply type/URL and company profile."

    def build_input(self, s):
        inp = {"searchQueries": s.core_words(), "maxItems": s.limit, "maxPages": 2, "includeDetails": False,
               "remoteOnly": s.remote}
        if s.place:
            inp["cities"] = [s.place.lower()]
        if s.only_new:
            inp.update(monitoringMode=True, monitorStateName=f"jobsearch-{nz.slug('-'.join(s.roles))}")
        return inp

    def normalize(self, it, s):
        if it.get("type") not in (None, "job"):
            return None
        external = nz.first(it.get("externalApplyUrl"), it.get("applyUrl") if it.get("applyType") == "external" else None)
        types = it.get("employmentTypes")
        return self.job(it, id=it.get("jobId"), title=it.get("title"), company=it.get("companyName"),
                        url=nz.first(it.get("jobUrl"), it.get("sourceUrl"), it.get("applyUrl")), location=it.get("location"),
                        remote=it.get("remote"), posted=nz.first(it.get("postedDate"), it.get("postedAt"), it.get("datePosted")),
                        salary=nz.first(it.get("salaryRaw"), it.get("salary") if isinstance(it.get("salary"), str) else None) or "",
                        apply_url=external or "", easy=True, tags=it.get("skills") or [],
                        description=nz.first(it.get("descriptionText"), it.get("description")),
                        employment_type=", ".join(types) if isinstance(types, list) else nz.first(it.get("employmentType"), it.get("contractType")))


class Hirist(Source):
    key, label, actor = "hirist", "Hirist", "logiover/hirist-tech-scraper"
    site = ("hirist.tech", "hirist.com")
    start_usd, item_usd = 0.0, 0.003
    region = "India"
    blurb = "Hirist.tech IT jobs with salary and skills."
    stale_risk = True  # no date filter: often returns jobs older than your window
    CITIES = {"bengaluru": "bangalore", "gurugram": "gurgaon", "new delhi": "delhi", "trivandrum": "kochi"}
    ALLOWED = {"bangalore", "delhi", "mumbai", "hyderabad", "pune", "chennai", "noida", "gurgaon", "kolkata", "ahmedabad",
               "jaipur", "indore", "chandigarh", "coimbatore", "kochi", "remote", "anywhere in india"}

    def build_input(self, s):
        inp = {"keywords": s.roles or [""], "maxJobs": s.limit, "maxPages": 2, "scrapeDetails": False}
        c = self.CITIES.get(s.place.lower(), s.place.lower()) if s.place else ""
        if s.remote:
            c = "remote"
        if c in self.ALLOWED:
            inp["cities"] = [c]
        if s.years is not None:
            y = s.years
            inp["experience"] = "0-2" if y < 2 else "2-5" if y < 5 else "5-10" if y < 10 else "10+"
        return inp

    def normalize(self, it, s):
        sal = "" if it.get("salaryHidden") else nz.first(it.get("salaryRaw"), nz.money(it.get("salaryMin"), it.get("salaryMax")))
        return self.job(it, id=it.get("jobId"), title=it.get("title"), company=it.get("company"), url=it.get("url"),
                        location=it.get("location"), remote=it.get("isRemote"), posted=it.get("postedAt"),
                        exp=(it.get("experienceMin"), it.get("experienceMax")) if it.get("experienceMin") is not None else it.get("experienceRaw"),
                        salary=sal or "", easy=True, tags=it.get("skills") or [])


class IndiaFeed(Source):
    key, label, actor = "india-feed", "India boards", "getascraper/india-job-inventory-feed"
    start_usd, item_usd = 0.00005, 0.00199
    region = "India"
    blurb = "One run across Naukri, Foundit, Indeed, LinkedIn, Shine, Hirist (no extra child-actor fees)."
    # Boards that run inside the feed (no second charge). Apna/CutShort/Internshala/Instahyre bill extra.
    BOARDS = ["naukri", "foundit", "indeed", "linkedin", "shine", "hirist"]
    HOSTS = ("naukri.com", "foundit.in", "indeed.com", "indeed.co.in", "linkedin.com", "shine.com", "hirist.tech",
             "hirist.com", "apna.co", "cutshort.io", "internshala.com", "instahyre.com", "wellfound.com", "workindia.in")
    site = HOSTS

    def build_input(self, s):
        boards = self.BOARDS
        inp = {"sources": boards, "keyword": s.roles[0] if s.roles else "", "postedWithinDays": s.days,
               "includeDetails": True, "uniqueOnly": True, "maxTotalRows": s.limit,
               "maxItemsPerSource": max(3, math.ceil(s.limit / len(boards))), "maxPagesPerSource": 2,
               "remoteOnly": s.remote}
        if s.place:
            inp["locations"] = [s.place]
        if s.years is not None:
            inp["maxExperienceYears"] = int(s.years) + 1
        if s.only_new:
            inp.update(outputMode="changesOnly", monitorScope=f"jobsearch-{nz.slug('-'.join(s.roles))}")
        return inp

    def normalize(self, it, s):
        board = str(it.get("sourcePlatform") or it.get("source") or "").strip()
        label = {"foundit": "Foundit", "linkedin": "LinkedIn", "naukri": "Naukri", "indeed": "Indeed", "shine": "Shine",
                 "hirist": "Hirist", "apna": "Apna", "cutshort": "CutShort", "internshala": "Internshala",
                 "instahyre": "Instahyre", "wellfound": "Wellfound", "workindia": "WorkIndia", "unstop": "Unstop"}.get(board.lower(), board.title() or self.label)
        company = it.get("company")
        if isinstance(company, dict):
            company = company.get("name")
        sal = nz.first(it.get("salaryRaw"), nz.money(it.get("salaryMin"), it.get("salaryMax"), it.get("salaryCurrency", ""), it.get("salaryPeriod", "")))
        exp = (it.get("experienceMin"), it.get("experienceMax")) if it.get("experienceMin") is not None else it.get("experienceText")
        return self.job(it, id=nz.first(it.get("listingKey"), it.get("sourceRecordId")), title=it.get("title"), company=company,
                        url=nz.first(it.get("listingUrl"), it.get("url"), it.get("sourceUrl")), location=it.get("location"),
                        remote=it.get("isRemote"), posted=it.get("postedAt"), applicants=it.get("applicants"), exp=exp,
                        salary=sal or "", apply_url=it.get("applicationUrl") or "", easy=False,
                        tags=it.get("skills") or [], description=it.get("description"), label=label)


# ====================================================================== Startups / remote / company sites
class Wellfound(Source):
    key, label, actor = "wellfound", "Wellfound", "blackfalcondata/wellfound-scraper"
    site = ("wellfound.com", "angel.co")
    start_usd, item_usd = 0.005, 0.003
    blurb = "Startup jobs with salary and equity ranges."

    def build_input(self, s):
        inp = {"query": s.roles[0] if s.roles else "", "maxResults": s.limit, "maxPages": 2,
               "maxAgeMinutes": s.hours * 60, "descriptionFormat": "text", "descriptionMaxLength": 5000}
        if s.remote:
            inp["remote"] = True
        elif s.place or s.location:
            inp["location"] = [nz.slug(s.place or s.location)]
        if s.only_new:
            inp.update(incrementalMode=True, stateKey=f"jobsearch-{nz.slug(inp['query'])}")
        return inp

    def normalize(self, it, s):
        locs = it.get("locationNames") or []
        loc = ", ".join(locs) if isinstance(locs, list) else str(locs)
        if it.get("remote") and "remote" not in loc.lower():
            loc = f"Remote{', ' + loc if loc else ''}"
        return self.job(it, id=it.get("id"), title=it.get("title"), company=it.get("companyName"),
                        url=nz.first(it.get("portalUrl"), it.get("detailUrl")), location=loc, remote=it.get("remote"),
                        posted=nz.first(it.get("postedAt"), it.get("datePosted")),
                        exp=(it.get("yearsExperienceMin"), it.get("yearsExperienceMax")) if it.get("yearsExperienceMin") is not None else None,
                        salary=it.get("compensation") or "", easy=True, tags=it.get("skills") or [],
                        description=nz.first(it.get("description"), it.get("descriptionMarkdown")), employment_type=it.get("jobType"))


class CareerSites(Source):
    key, label, actor = "career-sites", "Career site", "fantastic-jobs/career-site-job-listing-feed"
    start_usd, item_usd = 0.10, 0.0025
    min_items = 200
    blurb = "Direct postings from 275k company career sites (Workday, Greenhouse...). Minimum 200 jobs/run: ~$0.60."
    stale_risk = True

    def build_input(self, s):
        inp = {"limit": self.items_cap(s), "titleSearch": s.roles, "descriptionType": "text", "removeAgency": True}
        loc = s.city or s.location
        if loc and not s.remote:
            inp["locationSearch"] = [f"{s.city}, {s.country}" if s.city and s.country else loc]
        if s.remote:
            inp["aiWorkArrangementFilter"] = ["Remote OK", "Remote Solely"]
        if s.years is not None:
            y = s.years
            inp["aiExperienceLevelFilter"] = ["0-2"] if y < 2 else ["0-2", "2-5"] if y < 4 else ["2-5", "5-10"] if y < 9 else ["5-10", "10+"]
        return inp

    def normalize(self, it, s):
        locs = it.get("locations_derived") or it.get("cities_derived") or []
        loc = "; ".join(str(l) for l in locs[:2]) if isinstance(locs, list) else str(locs)
        wa = it.get("ai_work_arrangement") or ""
        sal = nz.money(it.get("ai_salary_min_value") or it.get("ai_salary_value"), it.get("ai_salary_max_value"),
                       it.get("ai_salary_currency", ""), it.get("ai_salary_unit_text", ""))
        exp = it.get("ai_experience_level")
        return self.job(it, id=it.get("id"), title=it.get("title"), company=it.get("organization"), url=it.get("url"),
                        location=f"{loc}{' · ' + wa if wa and 'remote' in wa.lower() else ''}", remote="remote" in wa.lower() or None,
                        posted=nz.first(it.get("date_posted"), it.get("date_created")), exp=f"{exp} yrs" if exp else None,
                        salary=sal, apply_url=it.get("url"), kind="company", tags=it.get("ai_key_skills") or [],
                        description=it.get("description_text"),
                        employment_type=", ".join(it.get("employment_type") or []) if isinstance(it.get("employment_type"), list) else it.get("employment_type"))


class RemoteJobs(Source):
    key, label, actor = "remote", "Hirebase", "hirebase/remote-jobs"
    start_usd, item_usd = 0.001, 0.005
    blurb = "Remote jobs straight from company career pages (230k+), with apply links."

    def build_input(self, s):
        inp = {"jobTitles": s.roles, "postedWithinDays": s.days, "maxResults": s.limit, "sortBy": "date_posted",
               "sortOrder": "desc", "dedupeBy": "companyAndTitle"}
        if s.years is not None:
            inp.update(yoeMax=int(math.ceil(s.years + 1)), includeJobsWithoutYoe=True)
        if s.only_new:
            inp["onlyNewSinceLastRun"] = True
        return inp

    def normalize(self, it, s):
        yoe = it.get("yearsOfExperience") or {}
        sr = it.get("salaryRange") or {}
        loc = nz.first(it.get("location"), it.get("locationType"), "Remote")
        if "remote" not in str(loc).lower() and str(it.get("locationType", "")).lower() == "remote":
            loc = f"Remote · {loc}"
        return self.job(it, id=nz.first(it.get("id"), it.get("jobSlug")), title=nz.first(it.get("jobTitle"), it.get("jobTitleRaw")),
                        company=it.get("companyName"), url=nz.first(it.get("jobBoardLink"), it.get("applicationLink")),
                        location=loc, remote=str(it.get("locationType", "")).lower() == "remote" or None, posted=it.get("datePosted"),
                        exp=(yoe.get("min"), yoe.get("max")) if isinstance(yoe, dict) and yoe.get("min") is not None else None,
                        salary=nz.money(sr.get("min"), sr.get("max"), sr.get("currency", ""), sr.get("period", "")) if isinstance(sr, dict) else "",
                        apply_url=it.get("applicationLink") or "", kind="company",
                        tags=list(it.get("skills") or []) + list(it.get("technologies") or []),
                        description=it.get("descriptionText"), employment_type=it.get("jobType"))


class WeWorkRemotely(Source):
    key, label, actor = "weworkremotely", "We Work Remotely", "inlifeprojects/weworkremotely-jobs-scraper"
    site = ("weworkremotely.com",)
    start_usd, item_usd = 0.00005, 0.001
    blurb = "Remote jobs from We Work Remotely's category feeds (company apply links)."
    stale_risk = True
    CATS = {"devops": ["devops"], "software": ["programming-all"], "data": ["programming-all"], "qa": ["programming-all"],
            "mobile": ["programming-all"], "security": ["devops", "programming-all"], "design": ["design"],
            "management": ["product"], "network": ["devops"]}

    def build_input(self, s):
        words = s.core_words()
        return {"categories": self.CATS.get(s.family, ["all"]), "keywordFilter": words[0] if words else "",
                "maxResults": s.limit, "filterNonTech": s.family not in ("business", "support", "design", "management")}

    def normalize(self, it, s):
        return self.job(it, id=it.get("id"), title=it.get("title"), company=it.get("company_name"),
                        url=nz.first(it.get("source_url"), it.get("id")), location=f"Remote · {it.get('location') or 'Worldwide'}",
                        remote=True, posted=it.get("posted_at"),
                        salary=nz.money(it.get("salary_min"), it.get("salary_max"), it.get("currency", ""), it.get("salary_period", "")),
                        apply_url=it.get("apply_url") or "", easy=False, tags=it.get("tags") or [],
                        description=it.get("description"), employment_type=it.get("type"))


# ====================================================================== Freelance
class Upwork(Source):
    key, label, actor = "upwork", "Upwork", "blackfalcondata/upwork-scraper"
    site = ("upwork.com",)
    start_usd, item_usd = 0.001, 0.001
    blurb = "Freelance Upwork jobs with client spend, rating and proposal counts."

    def build_input(self, s):
        q = s.roles[0] if len(s.roles) == 1 else " OR ".join(f'"{r}"' for r in s.roles)
        inp = {"query": q, "sort": "recency", "maxResults": s.limit, "maxAgeMinutes": s.hours * 60,
               "descriptionFormat": "text", "descriptionMaxLength": 4000}
        if s.only_new:
            inp["incrementalMode"] = True
        return inp

    def normalize(self, it, s):
        jt = str(it.get("jobType") or "").upper()
        if jt == "HOURLY" or it.get("hourlyBudgetMin"):
            pay = nz.money(it.get("hourlyBudgetMin"), it.get("hourlyBudgetMax"), "USD", "hour")
        else:
            pay = nz.money(it.get("budgetAmount"), None, "USD") + (" fixed" if it.get("budgetAmount") else "")
        lvl = re.sub(r"Level$", "", str(it.get("experienceLevel") or ""))
        url = it.get("url") or (f"https://www.upwork.com/jobs/~0{it['jobId']}" if it.get("jobId") else "")
        n = it.get("totalApplicants")
        return self.job(it, id=it.get("jobId"), title=it.get("title"), company=f"Upwork client{' · ' + it['clientCountry'] if it.get('clientCountry') else ''}",
                        url=url, location=f"Remote · client in {it.get('clientCountry') or 'unknown'}", remote=True,
                        posted=nz.first(it.get("publishTime"), it.get("createTime")),
                        applicants=n, exp=None, salary=pay, easy=True, tags=it.get("skills") or [],
                        description=it.get("description"), employment_type=f"Freelance{' · ' + lvl if lvl else ''}")


class UpworkNeatrat(Source):
    key, label, actor = "upwork-neatrat", "Upwork", "neatrat/upwork-job-scraper"
    site = ("upwork.com",)
    start_usd, item_usd = 0.0, 0.0035
    blurb = "Freelance Upwork jobs, newest first (one results page per run)."

    def items_cap(self, s):
        return 10 if s.limit <= 10 else 20 if s.limit <= 20 else 50

    def build_input(self, s):
        return {"query": s.roles[0] if s.roles else "", "sort": "newest", "page": 1, "pagesToScrape": 1,
                "perPage": self.items_cap(s)}

    def normalize(self, it, s):
        return self.job(it, id=it.get("id"), title=it.get("title"),
                        company=f"Upwork client{' · ' + it['clientLocation'] if it.get('clientLocation') else ''}",
                        url=it.get("url"), location=f"Remote · client in {it.get('clientLocation') or 'unknown'}", remote=True,
                        posted=nz.first(it.get("absoluteDate"), it.get("relativeDate")), applicants=it.get("proposals"),
                        salary=it.get("budget") or "", easy=True, tags=it.get("tags") or [], description=it.get("description"),
                        employment_type=f"Freelance · {it.get('jobType') or ''} {it.get('experienceLevel') or ''}".strip(" ·"))


ALL = [LinkedIn(), Naukri(), NaukriMemo(), NaukriMK(), IndiaFeed(), Instahyre(), InstahyreMemo(), Hirist(),
       Wellfound(), RemoteJobs(), WeWorkRemotely(), CareerSites(), Upwork(), UpworkNeatrat()]
BY_KEY = {s.key: s for s in ALL}
DEFAULT_KEYS = [s.key for s in ALL if s.default]

# Apify's own IDs for these actors: your run history lists runs by ID, so this is how
# "used this month" is matched to a source.
ACTOR_IDS = {
    "crawlworks/linkedin-jobs-scraper": "PeTP8M7vkdTthJvqk",
    "blackfalcondata/naukri-jobs-feed": "xYOP3UjaS8w38lWM7",
    "memo23/naukri-scraper": "EYXvM0o2lS7rYzgey",
    "muhammetakkurtt/naukri-job-scraper": "alpcnRV9YI9lYVPWk",
    "getascraper/india-job-inventory-feed": "8hG15V7QtjKUpwAt3",
    "getascraper/instahyre-jobs-scraper": "M5Myh7i6WMTmfwMlw",
    "memo23/instahyre-jobs-scraper": "x4L8aure7aGcZKuiv",
    "logiover/hirist-tech-scraper": "q5tTHTH8EWpM3Fsea",
    "blackfalcondata/wellfound-scraper": "jV4Y8h6j3AqVj5Qur",
    "hirebase/remote-jobs": "mCX6uPfZ7OjMV2ML7",
    "inlifeprojects/weworkremotely-jobs-scraper": "NDHGFmMLqb2TCHT4X",
    "fantastic-jobs/career-site-job-listing-feed": "Dn2KJLnaNC5vFGkEw",
    "blackfalcondata/upwork-scraper": "FlbDgNCfA8bOdFQWT",
    "neatrat/upwork-job-scraper": "XYTgO05GT5qAoSlxy",
}
for _s in ALL:
    _s.actor_id = ACTOR_IDS.get(_s.actor, "")


def parse_picks(text, current):
    """What the user typed at the source menu -> list of source keys.

    Accepts numbers from the menu (1,2,5), ranges (1-4), source names, and 'all'
    (every source except career-sites, which bills at least 200 jobs a run). Empty keeps `current`."""
    t = str(text or "").strip().lower()
    if not t:
        return list(current)
    keys = []
    for part in (p for p in re.split(r"[,\s]+", t) if p):
        m = re.fullmatch(r"(\d+)-(\d+)", part)
        if part in ("all", "a", "*"):
            keys += [s.key for s in ALL if s.key != "career-sites"]
        elif m or part.isdigit():
            lo, hi = (int(m.group(1)), int(m.group(2))) if m else (int(part), int(part))
            if not 1 <= lo <= hi <= len(ALL):
                raise ValueError(f"'{part}' isn't in the list: use 1 to {len(ALL)}")
            keys += [ALL[n - 1].key for n in range(lo, hi + 1)]
        elif part in BY_KEY:
            keys.append(part)
        else:
            raise ValueError(f"'{part}' isn't a number from the list or a source name")
    return list(dict.fromkeys(keys))


def resolve(keys):
    """'linkedin,naukri' or ['all'] -> [Source]; unknown keys raise ValueError with the valid list."""
    if isinstance(keys, str):
        keys = [k for k in re.split(r"[,\s]+", keys) if k]
    keys = keys or DEFAULT_KEYS
    if "all" in keys:
        return [s for s in ALL if s.key != "career-sites"]
    bad = [k for k in keys if k not in BY_KEY]
    if bad:
        raise ValueError(f"Unknown source(s): {', '.join(bad)}. Valid: {', '.join(BY_KEY)}")
    return [BY_KEY[k] for k in dict.fromkeys(keys)]
