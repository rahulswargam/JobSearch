"""Score each job against the resume, the same way the ranked sheet did.

    Resume Match       how much of the job's skill list you have, plus how close the title is (0-100)
    Interview Likelihood  experience asked vs yours, competition, location, seniority (0-100)
    Overall Fit        0.55 x Match + 0.45 x Likelihood
    Chance             High: Likelihood >= 65   Medium: 45-64   Low: below 45
"""
import re
from dataclasses import dataclass, field

from . import normalize as nz
from . import roles, skills

HIGH, MEDIUM = 65, 45


@dataclass
class Prefs:
    targets: list                      # role titles you're searching for
    preferred: list = field(default_factory=list)  # cities you'd work in
    home_city: str = ""
    country: str = ""
    min_match: int = 40                # below this a job isn't really your field: left out


def _fmt(x):
    return f"{x:g}" if x is not None else "?"


def _domain(profile):
    words = [w for w in re.split(r"\s+", profile.title or "") if w and w.lower() not in roles.GENERIC]
    return " ".join(words[:2]) or "relevant"


def match_score(job, profile, prefs):
    tags = job.get("skills") or []
    text_skills = skills.find_in_text(f"{job.get('title', '')}\n{job.get('description', '')}")
    ordered = list(dict.fromkeys(list(tags) + text_skills))
    in_title = set(skills.find_in_text(job.get("title", "")))
    mine = set(profile.skills)
    matched = [s for s in ordered if s in mine]
    missing = [s for s in ordered if s not in mine and s not in skills.SOFT_GAPS]
    w = lambda s: 2 if s in in_title else 1
    have, lack = sum(w(s) for s in matched), sum(w(s) for s in missing)
    title = roles.title_score(job.get("title", ""), prefs.targets, profile.family, mine)
    if have + lack == 0:
        score = 100 * 0.55 * title  # nothing to compare but the title
    else:
        coverage = have / (have + lack)
        confidence = min(1.0, (len(matched) + len(missing)) / 6)
        coverage = coverage * confidence + 0.45 * (1 - confidence)
        score = 100 * (0.65 * coverage + 0.35 * title)
        if title == 0:
            score = min(score, 45)  # a different kind of job that happens to share tools
    return round(max(0, min(100, score))), matched, missing, title


def likelihood_score(job, profile, prefs):
    score, notes = 70, []
    T, R = profile.years_total, profile.years_relevant or profile.years_total
    lo, hi = job.get("exp_min"), job.get("exp_max")
    ask = job.get("experience") or nz.years_label(lo, hi)
    dom = _domain(profile)
    if lo is None or T is None:
        if T is not None:
            score -= 5
            notes.append("No hard experience bar stated")
    elif lo <= R:
        score += 8
        notes.append(f"Asks {ask}: you meet it with {_fmt(R)}+ yrs {dom}")
    elif lo <= T:
        if lo - R <= 1.5:
            notes.append(f"Asks {ask}: close to your {_fmt(R)}+ yrs {dom} / {_fmt(T)} yrs total")
        else:
            score -= 8
            notes.append(f"Asks {ask}: count your {_fmt(T)} yrs total, lead with {dom} impact")
    elif lo <= T + 1:
        score -= 30
        notes.append(f"Asks {ask}: a stretch, apply only with a referral or strong cover note")
    elif lo <= T + 2:
        score -= 36
        notes.append(f"Asks {ask}: a stretch, apply only with a referral or strong cover note")
    elif lo <= T + 3:
        score -= 50
        notes.append(f"Asks {ask}: long shot on experience")
    else:
        score -= 58
        notes.append(f"Asks {ask}: long shot on experience")
    if hi is not None and T is not None and hi < T - 2.5:
        score -= 5
        notes.append("They may see you as overqualified")

    n = nz.applicants_count(job.get("applicants"))
    if n is not None:
        if n < 25:
            score += 4
            notes.append("Fewer than 25 applicants so far, apply early")
        elif n <= 100:
            score += 1
        elif n >= 200:
            score -= 8
            notes.append("200+ applicants, tailor the resume")

    loc, remote = job.get("location", ""), job.get("remote")
    city, country = roles.find_place(loc)
    if remote or re.search(r"\b(remote|work from home|wfh|anywhere)\b", loc, re.I):
        score += 2
        notes.append("Remote")
    elif city and prefs.home_city and roles.same_city(city, prefs.home_city):
        score += 5
        notes.append(f"In {city} (no relocation)")
    elif city and any(roles.same_city(city, p) for p in prefs.preferred):
        score += 2
        notes.append(f"In {city}")
    elif country and prefs.country and country != prefs.country:
        score -= 25
        notes.append(f"Based in {country}")
    elif city and prefs.preferred:
        score -= 3
        notes.append(f"In {city}, outside your preferred cities")

    title = job.get("title", "")
    if T is not None:
        if roles.VERY_SENIOR_WORDS.search(title) and T < 8:
            score -= 10
            notes.append("Very senior title for your experience")
        elif roles.SENIOR_WORDS.search(title) and T < 5:
            score -= 8
            notes.append("Senior title: pitch your strongest impact")
        elif roles.JUNIOR_WORDS.search(title) and T >= 3:
            score -= 10
            notes.append("Junior role: likely below your level")
    return max(0, min(100, round(score))), notes


def score(job, profile, prefs):
    if job.get("exp_min") is None and job.get("exp_max") is None:
        lo, hi = nz.years_in_text(job.get("description", ""))
        if lo is not None:
            job["exp_min"], job["exp_max"] = lo, hi
            job["experience"] = nz.years_label(lo, hi)
    m, matched, missing, title = match_score(job, profile, prefs)
    l, notes = likelihood_score(job, profile, prefs)
    if m >= 85 and any("long shot" in n or "stretch" in n for n in notes):
        notes.append("strong skill overlap though")
    overall = round(0.55 * m + 0.45 * l)
    chance = "High" if l >= HIGH else "Medium" if l >= MEDIUM else "Low"
    job.update(match=m, likelihood=l, score=overall, chance=chance, title_fit=title,
               skills_match=matched, skills_missing=missing, notes=notes, why="; ".join(notes),
               relevant=m >= prefs.min_match)
    return job
