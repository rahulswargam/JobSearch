"""The pipeline, independent of the command line so a web app can call the same functions.

    plan()     what each source will be asked, and what it may cost
    fetch()    run the actors (in parallel) and keep their raw rows
    collect()  raw rows -> normalized, fresh, de-duplicated, scored jobs
"""
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from . import normalize as nz
from . import roles, scoring
from .apify import Apify, ApifyError, run_cost
from .sources import Search


@dataclass
class Planned:
    source: object
    input: dict
    estimate: float
    cap_usd: float
    max_items: int


def plan(search, sources, budget=None):
    """Each source's actor input and cost estimate. The per-run spending cap is the estimate plus
    headroom; caps are shrunk proportionally so together they never exceed `budget`."""
    rows = []
    for src in sources:
        est = src.estimate(search)
        rows.append(Planned(src, src.build_input(search), est, cap_usd=round(est * 1.3 + 0.005, 4), max_items=src.items_cap(search)))
    caps = sum(r.cap_usd for r in rows)
    if budget and caps > budget:
        for r in rows:
            r.cap_usd = math.floor(budget * r.cap_usd / caps * 10000) / 10000
    return rows


def charged(src, run, items):
    """What a run cost. Apify books the per-job charges a moment after a run ends, so the run's own
    event counts often show only the start fee; this also counts the jobs actually returned."""
    starts = (run.get("chargedEventCounts") or {}).get("apify-actor-start") or 1
    by_rows = src.start_usd * starts + src.item_usd * len(items)
    return max(run_cost(run), by_rows)


def fetch(token, planned, raw_dir=None, log=print, parallel=3, timeout_secs=600, on_update=None):
    """Run every planned actor. Returns {source_key: {"items": [...], "run": {...}, "error": str|None, "cost": float}}.

    on_update(key, status, rows=None, cost=None, error=None) is called as each run moves along;
    without it, progress goes to `log` as text lines."""
    client = Apify(token)
    results = {}

    def note(key, status, **kw):
        if on_update:
            on_update(key, status, **kw)
        elif status in ("done", "failed"):
            msg = f"{kw.get('rows', 0)} rows" + (f", ~${kw['cost']:.4f}" if kw.get("cost") else "")
            log(f"  {key}: {kw.get('error') or 'done'} · {msg}")
        else:
            log(f"  {key}: {status}")

    def one(p):
        key = p.source.key
        note(key, "starting")
        try:
            items, run = client.run(p.source.actor, p.input, max_items=p.max_items, max_charge_usd=p.cap_usd,
                                    timeout_secs=timeout_secs, on_status=lambda st: note(key, st))
            status = run.get("status")
            err = None if status == "SUCCEEDED" else f"run {status.lower()}" + (" (partial results kept)" if items else "")
            return key, {"items": items, "run": _slim(run), "error": err, "cost": charged(p.source, run, items)}
        except ApifyError as e:
            return key, {"items": [], "run": {}, "error": str(e), "cost": 0.0}

    with ThreadPoolExecutor(max_workers=max(1, min(parallel, len(planned)))) as pool:
        futures = [pool.submit(one, p) for p in planned]
        for f in as_completed(futures):
            key, res = f.result()
            results[key] = res
            note(key, "failed" if res["error"] and not res["items"] else "done",
                 rows=len(res["items"]), cost=res["cost"], error=res["error"])
            if raw_dir:
                Path(raw_dir).mkdir(parents=True, exist_ok=True)
                (Path(raw_dir) / f"{key}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return results


def _slim(run):
    keep = ("id", "actId", "status", "startedAt", "finishedAt", "defaultDatasetId", "chargedEventCounts", "usageTotalUsd", "statusMessage")
    return {k: run.get(k) for k in keep if k in run}


def load_raw(raw_dir):
    out = {}
    for f in sorted(Path(raw_dir).glob("*.json")):
        try:
            out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return out


def collect(raw, search, profile, prefs, sources_by_key):
    """Normalize, drop stale and duplicate jobs, score. Returns (jobs sorted best-first, stats)."""
    jobs, stats = [], {"rows": 0, "stale": 0, "duplicates": 0, "unreadable": 0}
    for key, res in raw.items():
        src = sources_by_key.get(key)
        if not src:
            continue
        for it in res.get("items") or []:
            stats["rows"] += 1
            try:
                j = src.normalize(it, search) if isinstance(it, dict) else None
            except Exception:  # one odd row shouldn't sink the run
                j = None
            if not j:
                stats["unreadable"] += 1
                continue
            dt, has_time = nz.parse_date(j["posted_at"]) if j["posted_at"] else (None, False)
            if not nz.within(dt, j["posted_has_time"], search.hours):
                stats["stale"] += 1
                continue
            jobs.append(j)
    jobs, stats["duplicates"] = dedupe(jobs)
    for j in jobs:
        scoring.score(j, profile, prefs)
    jobs.sort(key=lambda j: (-j["score"], -j["match"]))
    return jobs, stats


def dedupe(jobs):
    """Same company + title + city on several boards -> keep the one with the company's own link."""
    best = {}
    for j in jobs:
        city = roles.find_place(j["location"])[0] or nz.norm_key(j["location"])[:12]
        k = (nz.norm_key(j["company"]), nz.norm_key(j["title"]), city.lower())
        cur = best.get(k)
        if cur is None:
            best[k] = j
            continue
        rank = lambda x: (bool(x["link"]), bool(x["description"]), bool(x["applicants"]), len(x["skills"]))
        keep, other = (j, cur) if rank(j) > rank(cur) else (cur, j)
        keep.setdefault("also_on", [])
        if other["source_label"] not in keep["also_on"] and other["source_label"] != keep["source_label"]:
            keep["also_on"].append(other["source_label"])
        best[k] = keep
    out = list(best.values())
    return out, len(jobs) - len(out)


def build_search(profile, cfg):
    """Search settings from config + profile."""
    location = cfg.get("location") or profile.country or profile.city or ""
    remote = bool(cfg.get("remote_only"))
    if location.strip().lower() in ("remote", "anywhere", "worldwide", "wfh"):
        remote, location = True, profile.country or ""
    city = roles.canonical_city(location) if roles.find_place(location)[0] else ""
    _, country = roles.find_place(location)
    return Search(
        roles=cfg.get("roles") or ([profile.title] if profile.title else []),
        location=location,
        city=city,
        country=country or profile.country,
        hours=int(cfg.get("posted_within_hours") or 24),
        limit=int(cfg.get("per_source") or 25),
        years=profile.years_total if not cfg.get("no_experience_filter") else None,
        remote=remote,
        only_new=bool(cfg.get("only_new")),
        family=profile.family,
    )


def build_prefs(profile, search, cfg):
    preferred = [roles.canonical_city(c) for c in (cfg.get("preferred_locations") or []) if c]
    if profile.city and profile.city not in preferred:
        preferred.insert(0, profile.city)
    return scoring.Prefs(targets=search.roles, preferred=preferred, home_city=profile.city,
                         country=profile.country or search.country, min_match=int(cfg.get("min_match") or 40))


def parse_window(text):
    """'24h', '3d', '1w', '30d' or a number of hours -> hours."""
    s = str(text).strip().lower()
    try:
        if s.endswith("h"):
            return int(float(s[:-1]))
        if s.endswith("d"):
            return int(float(s[:-1]) * 24)
        if s.endswith("w"):
            return int(float(s[:-1]) * 168)
        return int(float(s))
    except ValueError:
        raise ValueError(f"Can't read '{text}': use 24h, 3d, 7d or 30d")


def money(x):
    return f"${x:.2f}" if x >= 0.995 or x == 0 else f"${x:.3f}" if x >= 0.01 else f"${x:.4f}"
