"""Write the apply-links page (same look as the original job_links.html), plus JSON and CSV of every scored job."""
import csv
import json
from datetime import datetime
from pathlib import Path

TEMPLATE = Path(__file__).with_name("templates") / "job_links_template.html"
CARD_FIELDS = ("rank", "score", "chance", "match", "likelihood", "title", "company", "location", "posted", "applicants",
               "experience", "salary", "url", "kind", "link", "note", "source", "source_label", "why", "skills_match",
               "skills_missing", "also_on")


def window_label(hours):
    if hours <= 24:
        return "posted in the last 24 hours"
    if hours % 24 == 0:
        return f"posted in the last {hours // 24} days"
    return f"posted in the last {hours} hours"


def page_jobs(jobs):
    """High and Medium jobs that are in your field, ranked by overall fit."""
    keep = [j for j in jobs if j.get("relevant") and j.get("chance") in ("High", "Medium")]
    keep.sort(key=lambda j: (-j["score"], -j["match"]))
    out = []
    for i, j in enumerate(keep, 1):
        row = {k: j.get(k) for k in CARD_FIELDS}
        row["rank"] = i
        out.append({k: ("" if v is None else v) for k, v in row.items()})
    return out


def render(jobs, *, sources_used, hours, profile, generated=None):
    cards = page_jobs(jobs)
    generated = generated or datetime.now().strftime("%d %b %Y, %H:%M")
    names = list(dict.fromkeys(sources_used))
    data = {
        "generated": generated,
        "sheet": f"{' + '.join(names) or 'Apify'}, {window_label(hours)}",
        "footer": (f"Built {generated}. Scored against {profile.resume_file or 'your resume'}"
                   f"{' (' + profile.title + ')' if profile.title else ''}. "
                   f"Low-chance and off-field roles are left out. \"Mark applied\" is saved in this browser only."),
        "jobs": cards,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/{}", payload), cards


def write_all(jobs, out_dir, *, sources_used, hours, profile, meta=None):
    """Writes job_links.html, jobs.json, jobs.csv into out_dir. Returns (html path, number of cards)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    html, cards = render(jobs, sources_used=sources_used, hours=hours, profile=profile)
    page = out / "job_links.html"
    page.write_text(html, encoding="utf-8")
    slim = [{k: v for k, v in j.items() if k != "description"} for j in jobs]
    (out / "jobs.json").write_text(json.dumps({"meta": meta or {}, "profile": profile.to_dict(), "jobs": slim},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    cols = ["score", "chance", "match", "likelihood", "title", "company", "location", "posted", "applicants", "experience",
            "salary", "source_label", "url", "link", "skills_match", "skills_missing", "why"]
    with open(out / "jobs.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Overall Fit", "Interview Chance", "Resume Match", "Interview Likelihood", "Job Title", "Company", "Location",
                    "Posted", "Applicants", "Experience", "Salary", "Source", "Job Link", "Company Apply Link",
                    "Your Matching Skills", "Skills to Brush Up", "Why / Notes"])
        for j in jobs:
            w.writerow([", ".join(j.get(c) or []) if isinstance(j.get(c), list) else j.get(c, "") for c in cols])
    return page, len(cards)
