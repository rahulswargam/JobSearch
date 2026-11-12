"""Command line: find fresh jobs with Apify actors, score them against your resume, write job_links.html.

    python -m jobsearch                       guided search: API key, resume, sources, save folder, then run
    python -m jobsearch --dry-run             show what would run and what it may cost; spends nothing
    python -m jobsearch -y                    no menus: config.json, --resume and APIFY_TOKEN (scheduled runs)
    python -m jobsearch --resume cv.pdf --role "DevOps Engineer" --location India --sources linkedin,naukri
    python -m jobsearch credits               credit left, and what each source costs and has used
    python -m jobsearch change-key            save a different Apify API key as APIFY_TOKEN
    python -m jobsearch forget-key            remove APIFY_TOKEN from this computer
    python -m jobsearch profile               show what was read from your resume
    python -m jobsearch sources               list job sources, their actors and prices (offline)
    python -m jobsearch rescore <run folder>  re-score a past run (no Apify credits used)

The API key is pasted once and saved as the APIFY_TOKEN environment variable for your user account
(never in this project); every run reads it back from there. Your resume is only read, never saved.
"""
import argparse
import json
import os
import shutil
import sys
import threading
import webbrowser
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from . import core, keystore, report, resume, sources, ui
from . import normalize as nz
from .apify import Apify, ApifyError
from .ui import BLUE, GREEN, MUTED, RED, YELLOW, console

TOKEN_VARS = keystore.ENV_NAMES
RESUME_TYPES = (".pdf", ".docx", ".txt", ".md", ".text")
DEFAULTS = {"sources": sources.DEFAULT_KEYS, "per_source": 25, "posted_within": "24h", "min_match": 40, "max_cost_usd": 0.50}
SAVED_KEYS = ("roles", "location", "preferred_locations", "sources", "output_dir")  # never the resume, never the key
STEPS = 4


def default_output_dir():
    return ui.downloads_dir() / "JobSearch"


def output_dir(cfg):
    return Path(cfg["output_dir"]).expanduser() if cfg.get("output_dir") else default_output_dir()


class Quit(Exception):
    pass


def say(msg=""):
    console.print(msg, highlight=False, markup=False)


def interactive():
    return ui.interactive()


def split_list(text):
    return [x.strip() for x in str(text or "").split(",") if x.strip()]


# ---------------------------------------------------------------- config
def load_config(path, must_exist=True):
    p = Path(path) if path else Path("config.json")
    cfg = dict(DEFAULTS)
    cfg["_path"] = str(p)
    if p.is_file():
        try:
            user = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            raise Quit(f"{p} isn't valid JSON: {e}")
        cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
    elif path and must_exist:
        raise Quit(f"Config file not found: {p}")
    return cfg


def save_choices(cfg):
    """Remember search settings (role, place, cities, sources) in config.json. Never the resume or the key."""
    p = Path(cfg["_path"])
    try:
        raw = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except (OSError, ValueError):
        return
    new = dict(raw)
    new.update({k: cfg[k] for k in SAVED_KEYS if cfg.get(k)})
    if new != raw:
        try:
            p.write_text(json.dumps(new, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass


def merge_args(cfg, a):
    for attr, key in (("resume", "resume"), ("role", "roles"), ("location", "location"), ("prefer", "preferred_locations"),
                      ("sources", "sources"), ("per_source", "per_source"), ("posted", "posted_within"), ("out", "output_dir")):
        if getattr(a, attr, None):
            cfg[key] = getattr(a, attr)
    if getattr(a, "min_match", None) is not None:
        cfg["min_match"] = a.min_match
    if getattr(a, "budget", None) is not None:
        cfg["max_cost_usd"] = a.budget
    if getattr(a, "remote_only", False):
        cfg["remote_only"] = True
    if getattr(a, "only_new", False):
        cfg["only_new"] = True
    try:
        cfg["posted_within_hours"] = core.parse_window(cfg.get("posted_within", "24h"))
    except ValueError as e:
        raise Quit(str(e))
    return cfg


# ---------------------------------------------------------------- step 1: Apify key
def account_text(acct, source=None):
    t = Text.assemble(("Signed in to Apify as ", ""), (acct.get("username") or "your account", f"bold {BLUE}"))
    if acct.get("plan"):
        t.append(f" ({acct['plan']} plan)", style=MUTED)
    if acct.get("left") is not None:
        t.append(" · ")
        t.append_text(credit_text(acct))
    if source:
        t.append(f"  (key from {source})", style=MUTED)
    return t


def credit_text(acct):
    if acct.get("left") is None:
        return Text("Apify didn't report your credit", style=MUTED)
    left = acct["left"]
    colour = GREEN if left >= 1 else YELLOW if left >= 0.2 else RED
    t = Text.assemble((ui.money(left), f"bold {colour}"), (f" of {ui.money(acct['limit'])} credit left", ""))
    end, _ = nz.parse_date(acct.get("cycle_end"))
    if end:
        t.append(f" (resets {end.day} {end:%b})", style=MUTED)
    return t


def check_key(tok):
    """The account for a key, or None if Apify rejects it."""
    try:
        return Apify(tok).account()
    except ApifyError as e:
        if e.status == 401:
            return None
        raise Quit(str(e))


def enter_key():
    """Offer to open the Apify key page, take the key (hidden), check it, and register it once."""
    choice = ui.select("How do you want to add your API key?", [
        ("Open the Apify API key page in my browser", "Copy your key there, then come back and paste it here"),
        ("I have my key, let me paste it", "")], default=0)
    if choice == 0:
        webbrowser.open(ui.APIFY_KEY_PAGE)
        ui.gap()
        ui.info("The Apify key page is open in your browser. Copy your key, then paste it below.")
    ui.gap()
    for attempt in range(3):
        tok = ui.secret("Paste your Apify API key (hidden), then press Enter:  ")
        if not tok:
            raise Quit("No key entered; nothing was spent.")
        acct = check_key(tok)
        if acct:
            ui.gap()
            ui.ok(account_text(acct))
            try:
                where = keystore.save(tok)
                ui.ok(f"Key saved as {where}. You won't be asked for it again.")
            except Exception as e:  # the search still works this time
                ui.warn(f"Couldn't save the key as APIFY_TOKEN ({e}); you'll be asked again next time.")
            return tok, acct
        ui.error("Apify rejected that key. Copy the whole key and try again." if attempt < 2 else "Apify rejected that key.")
    raise Quit("Three keys were rejected; nothing was spent.")


def key_step(guided):
    """Read the key from the APIFY_TOKEN environment variable. If found: continue with it, or change it."""
    tok, where = keystore.find()
    if tok:
        acct = check_key(tok)
        if not acct:
            msg = f"The key in {where} no longer works (it was deleted or regenerated on Apify)."
            if not interactive():
                raise Quit(f"{msg} Run  python -m jobsearch change-key  in a terminal.")
            ui.warn(msg)
            ui.gap()
            return enter_key()
        ui.ok(Text.assemble(("API key found ", "bold"), (f"(from {where})", MUTED)))
        ui.ok(account_text(acct))
        if guided:
            ui.gap()
            choice = ui.select("Which API key should this search use?", [
                ("Continue with this key", f"{acct.get('username') or 'this account'}  ·  {ui.money(acct.get('left'))} credit left"),
                ("Change API key", "Use a different key, for example another Apify account with credit left")], default=0)
            if choice == 1:
                ui.gap()
                return enter_key()
        return tok, acct
    if not interactive():
        raise Quit("No API key found. Run  python -m jobsearch  once in a terminal to register your Apify key.")
    ui.warn(Text("No API key found", style="bold"))
    ui.gap()
    return enter_key()


# ---------------------------------------------------------------- step 2: resume
def clean_path(text):
    """A path as typed, pasted, or dragged into the terminal (PowerShell adds "& '...'")."""
    t = str(text or "").strip()
    if t.startswith("& "):
        t = t[2:].strip()
    return t.strip("\"'").strip()


def valid_resume(p):
    p = Path(clean_path(p)).expanduser()
    if not p.is_file():
        ui.error(f"Can't find a file at {p}")
        return None
    if p.suffix.lower() not in RESUME_TYPES:
        ui.error(f"{p.name} isn't a PDF, Word (.docx) or text file.")
        return None
    return str(p)


def resume_step(cfg):
    """Open the file window to choose the resume. Nothing about it is saved."""
    start = Path(cfg["resume"]).expanduser().parent if cfg.get("resume") else Path.home()
    ui.info("A file window is opening: choose your resume (PDF, Word or text).")
    while True:
        chosen = ui.pick_file("Choose your resume", str(start) if start and start.is_dir() else None)
        if chosen is None:
            ui.warn("A file window can't open here.")
            chosen = ui.ask_text("Paste the full path to your resume:")
        elif chosen == "":
            ui.gap()
            choice = ui.select("No file was chosen. What now?", ["Open the file window again", "Type the file path instead", "Quit"], 0)
            if choice == 2:
                raise Quit("Cancelled; nothing was spent.")
            if choice == 1:
                chosen = ui.ask_text("Paste the full path to your resume:")
            else:
                continue
        path = valid_resume(chosen) if chosen else None
        if path:
            ui.ok(Text.assemble(("Resume  ", "bold"), (Path(path).name, f"bold {BLUE}")))
            ui.gap()
            return path


def resume_path(cfg):
    path = cfg.get("resume")
    if not path:
        raise Quit("No resume given. Use --resume PATH (or run python -m jobsearch in a terminal to pick one).")
    return path


def load_profile(cfg):
    try:
        prof = resume.build_profile(resume_path(cfg), cfg.get("profile"))
    except resume.ResumeError as e:
        raise Quit(str(e))
    if not prof.title and not cfg.get("roles"):
        role = ui.ask_text("Couldn't tell your job title from the resume. What role are you looking for?")
        if not role:
            raise Quit("No role to search for. Use --role \"Job title\" or set \"roles\" in config.json.")
        cfg["roles"] = [role]
        prof.title = role
    return prof


def years_text(p):
    if p.years_total is None:
        return ""
    return f"{p.years_total:g} yrs total" + (f", {p.years_relevant:g} yrs as {p.title}" if p.years_relevant not in (None, p.years_total) else "")


def show_profile(p):
    g = Table.grid(padding=(0, 2))
    g.add_column(style=f"bold {BLUE}", no_wrap=True)
    g.add_column()
    skills = Text()
    for i, s in enumerate(p.skills[:18]):
        skills.append(f" {s} ", style=f"bold {[BLUE, GREEN, '#F29900', RED][i % 4]}")
    if len(p.skills) > 18:
        skills.append(f" +{len(p.skills) - 18} more", style=MUTED)
    g.add_row("Resume", Text(p.resume_file, style="bold"))
    g.add_row("Name", p.name or "-")
    g.add_row("Role", Text.assemble((p.title or "-", "bold"), (f"  ({p.family or 'unknown'} family)", MUTED)))
    g.add_row("Exp.", years_text(p) or Text("not found (set profile.years_total in config.json)", style=YELLOW))
    g.add_row("Based", ", ".join(x for x in (p.city, p.country) if x) or "-")
    g.add_row(f"Skills {len(p.skills)}", skills)
    console.print(Panel(g, title=Text(" Your resume ", style=f"bold white on {GREEN}"), title_align="left",
                        border_style=GREEN, expand=False, padding=(1, 3)))
    console.print()


def settings_step(cfg, prof, a):
    """Show what will be searched for; Enter accepts it, or change role, place and cities."""
    cfg.setdefault("roles", None)
    if not cfg.get("roles"):
        cfg["roles"] = [prof.title] if prof.title else []
    if not cfg.get("location"):
        cfg["location"] = prof.country or prof.city
    if not cfg.get("preferred_locations"):
        cfg["preferred_locations"] = [prof.city] if prof.city else []
    console.print(Text.assemble(("  Search for   ", MUTED), (" / ".join(cfg["roles"]) or "-", f"bold {BLUE}"),
                                ("   in   ", MUTED), (cfg["location"] or "anywhere", "bold"),
                                ("   ·   prefer   ", MUTED), (", ".join(cfg["preferred_locations"]) or "-", "bold")))
    ui.gap()
    if a.role and a.location:
        return
    if ui.select("Search settings", [("Looks good, continue", ""), ("Change the role, location or cities", "")], 0) == 1:
        ui.gap()
        cfg["roles"] = split_list(ui.ask_text("Role(s) to search for, comma separated:", ", ".join(cfg["roles"]))) or cfg["roles"]
        cfg["location"] = ui.ask_text("Where to search (a country covers all of it, or Remote):", cfg["location"])
        cfg["preferred_locations"] = split_list(ui.ask_text("Cities you'd work in, comma separated:", ", ".join(cfg["preferred_locations"])))


# ---------------------------------------------------------------- step 4: where to save
def save_step(cfg):
    """Where the job links page goes. Default: Downloads/JobSearch, or the folder chosen last time.
    'Choose another folder' opens a folder window and fills the chosen path in, ready to confirm."""
    current = output_dir(cfg)
    console.print(Text.assemble(("  The job links page will be saved in   ", MUTED), (str(current), f"bold {BLUE}")))
    ui.gap()
    while True:
        choice = ui.select("Where should the job links page be saved?", [
            ("Save it here", str(current)),
            ("Choose another folder", "A folder window opens; the path you pick is filled in for you")], 0)
        if choice == 0:
            break
        start = current if current.is_dir() else (current.parent if current.parent.is_dir() else Path.home())
        picked = ui.pick_folder("Choose where to save the job links page", str(start))
        ui.gap()
        if picked is None:
            ui.warn("A folder window can't open here; type the folder instead.")
            picked = str(current)
        elif picked == "":
            ui.info("No folder chosen; keeping the one above.")
            ui.gap()
            continue
        typed = clean_path(ui.ask_text("Save to (Enter to confirm, or edit the path):", picked))
        current = Path(typed or picked).expanduser()
        break
    try:
        current.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise Quit(f"Can't create {current}: {e}")
    cfg["output_dir"] = str(current)
    return current


# ---------------------------------------------------------------- step 3: sources
BOARDS = {"linkedin": "LinkedIn", "naukri": "Naukri (cheapest)", "naukri-memo23": "Naukri + company links",
          "naukri-mk": "Naukri (basic)", "india-feed": "6 Indian job boards", "instahyre": "Instahyre",
          "instahyre-memo23": "Instahyre + apply links", "hirist": "Hirist.tech", "wellfound": "Wellfound startups",
          "remote": "Remote, company sites", "weworkremotely": "We Work Remotely", "career-sites": "Company career sites",
          "upwork": "Upwork freelance", "upwork-neatrat": "Upwork (one page)"}


def usage_cells(src, search, acct, used_by):
    est = src.estimate(search)
    left = acct.get("left") if acct else None
    runs = "-" if left is None or not est else f"{int(left // est):,}"
    u = used_by.get(src.actor_id)
    used = f"{u['runs']} run{'s' if u['runs'] != 1 else ''} · {ui.money(u['usd'])}" if u else "-"
    return est, runs, used


def sources_step(cfg, search, tok, acct):
    """Tick the sources; the line under the list shows how much will be debited as you tick."""
    used_by = Apify(tok).usage_by_actor(acct.get("cycle_start")) if tok else {}
    console.print(Text.assemble(("  ", ""), credit_text(acct) if acct else Text("Credit unknown", style=MUTED),
                                (".  Apify credit is one balance shared by every source.", MUTED)))
    ui.gap()
    current = set(s.key for s in sources.resolve(cfg.get("sources")))
    cap = float(cfg.get("max_cost_usd") or 0) or None
    left = acct.get("left") if acct else None
    est = {}
    rows = []
    for src in sources.ALL:
        e, runs, used = usage_cells(src, search, acct, used_by)
        est[src.key] = e
        note = "min 200 jobs, mostly older" if src.key == "career-sites" else "may include older jobs" if src.stale_risk else ""
        rows.append((src.key, [src.key, BOARDS.get(src.key, src.label), ui.money(e), runs, used], note))
    columns = [("source", 17, "left", None), ("board", 23, "left", None), ("per run", 8, "right", "cost"),
               ("runs left", 9, "right", None), ("used this month", 16, "left", None)]

    def footer(keys):
        total = sum(est[k] for k in keys)
        out = [("", f"  Selected {len(keys)} of {len(rows)}  ·  "), ("class:cost", f"up to {ui.money(total)} will be debited")]
        if left is not None:
            after = left - total
            out += [("", "  ·  credit "), ("class:ok", ui.money(left)), ("", " → about "),
                    ("class:ok" if after >= 0 else "class:bad", ui.money(max(0.0, after)))]
        if left is not None and total > left:
            out += [("", "\n"), ("class:bad", "  That's more than the credit you have left: pick fewer, or switch account at the next step.")]
        elif cap and total > cap:
            out += [("", "\n"), ("class:warn", f"  Over your {ui.money(cap)} per-search cap: you'll be asked whether to raise it.")]
        return out

    picked = ui.checkbox("Which job sources should this search use?", columns, rows, current, footer,
                         answer=lambda ks: f"{len(ks)} source{'s' if len(ks) != 1 else ''} · up to {ui.money(sum(est[k] for k in ks))}")
    cfg["sources"] = picked
    return picked


# ---------------------------------------------------------------- plan, confirm, run
def show_plan(search, prefs, planned):
    console.print(Text.assemble(("  Search   ", f"bold {BLUE}"), (" / ".join(search.roles), "bold"),
                                (f" · {search.location or 'anywhere'} · {report.window_label(search.hours)}", ""),
                                (" · remote only" if search.remote else "", ""), (" · only new since last run" if search.only_new else "", "")))
    console.print(Text.assemble(("  Prefer   ", f"bold {BLUE}"), (", ".join(prefs.preferred) or "-", "")))
    t = ui.table("source", "actor", ("max jobs", "right"), ("up to", "right", "#F29900"))
    for p in planned:
        t.add_row(Text(p.source.key, style="bold"), Text(p.source.actor, style=MUTED), str(p.max_items), ui.money(p.estimate))
    total = sum(p.estimate for p in planned)
    t.add_row("", Text("total  (free-plan prices; paid plans cost less)", style=MUTED), "", Text(ui.money(total), style="bold #F29900"))
    console.print()
    console.print(ui.indent(t))
    return total


def budget_step(search, srcs, cfg, tok, acct, guided):
    """Fit the search to the per-search cap and to the credit left; offer to switch account if short."""
    while True:
        cap = float(cfg.get("max_cost_usd") or 0) or None
        total = sum(s.estimate(search) for s in srcs)
        left = acct.get("left") if acct else None
        if left is not None and left < 0.001:
            if not guided:
                raise Quit("This Apify account has no credit left this month. Nothing was run.")
            if ui.select("This Apify account has no credit left this month.",
                         [("Change API key", "Use another Apify account with credit left"), ("Quit", "")], 0) == 1:
                raise Quit("Cancelled; nothing was spent.")
            ui.gap()
            tok, acct = enter_key()
            ui.gap()
            continue
        if left is not None and total > left:
            if not guided:
                return tok, acct, left, f"you have {ui.money(left)} Apify credit left"
            choice = ui.select(f"Up to {ui.money(total)} is more than the {ui.money(left)} credit left on this account.", [
                ("Change API key", "Switch to another Apify account with more credit"),
                ("Run anyway with smaller limits", f"Sources return fewer jobs to stay within {ui.money(left)}"),
                ("Cancel", "Nothing is spent")], 0)
            ui.gap()
            if choice == 0:
                tok, acct = enter_key()
                ui.gap()
                continue
            if choice == 2:
                raise Quit("Cancelled; nothing was spent.")
            return tok, acct, left, f"you have {ui.money(left)} Apify credit left"
        if cap and total > cap:
            if not guided:
                return tok, acct, cap, f"your cap is {ui.money(cap)} per search (raise it with --budget)"
            choice = ui.select(f"Up to {ui.money(total)} is over your {ui.money(cap)} per-search cap.", [
                (f"Raise the cap to {ui.money(total)} for this search", "Every source can return all its jobs"),
                (f"Keep the {ui.money(cap)} cap", "Sources return fewer jobs")], 0)
            ui.gap()
            if choice == 0:  # no per-search cap this time; never more than the credit left
                return tok, acct, left, None
            return tok, acct, cap, f"your cap is {ui.money(cap)} per search"
        return tok, acct, cap, None


class RunBoard:
    """Live table while the actors run."""

    def __init__(self, planned):
        self.rows = {p.source.key: {"actor": p.source.actor, "status": "waiting", "rows": None, "cost": None, "error": None}
                     for p in planned}
        self.lock = threading.Lock()

    def update(self, key, status, rows=None, cost=None, error=None):
        with self.lock:
            r = self.rows[key]
            r["status"] = status
            if rows is not None:
                r["rows"] = rows
            if cost is not None:
                r["cost"] = cost
            if error:
                r["error"] = error

    def __rich__(self):
        t = ui.table("source", "actor", "status", ("jobs", "right"), ("cost", "right", "#F29900"))
        with self.lock:
            for key, r in self.rows.items():
                st = r["status"]
                if st == "done":
                    status = Text("✔ done" + (f" ({r['error']})" if r["error"] else ""), style=f"bold {GREEN}")
                elif st == "failed":
                    status = Text("✘ " + str(r["error"] or "failed")[:60], style=f"bold {RED}")
                elif st == "waiting":
                    status = Text("waiting", style=MUTED)
                else:
                    status = Spinner("dots", text=Text(" " + st, style=BLUE), style=BLUE)
                t.add_row(Text(key, style="bold"), Text(r["actor"], style=MUTED), status,
                          "" if r["rows"] is None else str(r["rows"]), "" if r["cost"] is None else ui.money(r["cost"]))
        return ui.indent(t)


def run_actors(tok, planned, run_dir):
    if interactive():
        board = RunBoard(planned)
        with Live(board, console=console, refresh_per_second=10, transient=False):
            return core.fetch(tok, planned, raw_dir=run_dir / "raw", on_update=board.update)
    return core.fetch(tok, planned, raw_dir=run_dir / "raw", log=say)


# ---------------------------------------------------------------- commands
def cmd_sources(a):
    s = sources.Search(roles=["x"], limit=25)
    t = ui.table("#", "source", "region", "actor", ("25 jobs up to", "right", "#F29900"), "about")
    for i, src in enumerate(sources.ALL, 1):
        about = src.blurb + (" (default)" if src.default else "")
        t.add_row(str(i), Text(src.key, style="bold"), src.region, Text(src.actor, style=MUTED), ui.money(src.estimate(s)), about)
    console.print(ui.indent(t))
    say("Free-plan prices; paid Apify plans are cheaper. For your credit and usage per source:  python -m jobsearch credits")


def cmd_profile(a):
    cfg = merge_args(load_config(a.config), a)
    if not cfg.get("resume") and interactive():
        cfg["resume"] = resume_step(cfg)
    show_profile(load_profile(cfg))


def cmd_credits(a):
    cfg = merge_args(load_config(a.config), a)
    if interactive():
        ui.banner()
    tok, acct = key_step(guided=False)
    search = sources.Search(roles=["x"], limit=int(cfg.get("per_source") or 25))
    used_by = Apify(tok).usage_by_actor(acct.get("cycle_start"))
    t = ui.table("#", "source", "actor", ("per run", "right", "#F29900"), ("runs left", "right"), "used this month")
    for i, src in enumerate(sources.ALL, 1):
        est, runs, used = usage_cells(src, search, acct, used_by)
        t.add_row(str(i), Text(src.key, style="bold"), Text(src.actor, style=MUTED), ui.money(est), runs, used)
    console.print()
    console.print(ui.indent(t))
    say(f"per run = the most one search of {search.limit} jobs can cost · runs left = how many your remaining credit covers")


def cmd_change_key(a):
    if not interactive():
        raise Quit("change-key asks for your key; run it in a terminal.")
    ui.banner()
    enter_key()
    ui.credit_footer()


def cmd_forget_key(a):
    if keystore.forget():
        ui.ok("The APIFY_TOKEN environment variable was removed. You'll be asked for a key next time.")
    else:
        ui.info("APIFY_TOKEN wasn't set.")
    others = [n for n in keystore.ENV_NAMES[1:] if os.environ.get(n)]
    if others:
        ui.info(f"{others[0]} is still set in this terminal and will be used.")


def cmd_init(a):
    if not interactive():
        raise Quit("init asks questions; run it in a terminal.")
    path = Path(a.config or "config.json")
    old = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    cfg = {k: v for k, v in old.items() if k != "resume"}
    ui.info(f"Creating {path}. Your resume is only read to suggest answers; its path is not saved.")
    prof = resume.build_profile(resume_step({}), old.get("profile"))
    show_profile(prof)
    cfg["roles"] = split_list(ui.ask_text("Roles to search, comma separated:", ", ".join(old.get("roles") or [prof.title])))
    cfg["location"] = ui.ask_text("Search location (a country searches everywhere in it):", old.get("location") or prof.country or prof.city)
    cfg["preferred_locations"] = split_list(ui.ask_text("Cities you'd work in, comma separated:", ", ".join(old.get("preferred_locations") or [prof.city])))
    cfg["per_source"] = int(ui.ask_text("Max jobs per source (you pay per job):", str(old.get("per_source", 25))))
    cfg["posted_within"] = ui.ask_text("Only jobs posted within (24h, 3d, 7d):", old.get("posted_within", "24h"))
    cfg["max_cost_usd"] = float(ui.ask_text("Spending cap per search, USD:", str(old.get("max_cost_usd", 0.5))))
    cfg.setdefault("sources", sources.DEFAULT_KEYS)
    cfg.setdefault("min_match", 40)
    cfg.setdefault("profile", {"years_total": None, "years_relevant": None, "extra_skills": [], "ignore_skills": []})
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    ui.ok(f"Saved {path}. Now run:  python -m jobsearch")


def cmd_search(a):
    guided = interactive() and not a.yes and not a.dry_run
    cfg = merge_args(load_config(a.config, must_exist=not guided), a)
    if interactive():
        ui.banner()
    tok = acct = None

    # Step 1 · Apify key: look for one first, offer another account's key
    if not a.dry_run:
        if guided:
            ui.step(1, STEPS, "Apify API key")
        tok, acct = key_step(guided)

    # Step 2 · Resume (file window) and what to search for
    if guided:
        ui.step(2, STEPS, "Your resume")
        if a.resume:
            ui.ok(f"Resume: {a.resume}  (from --resume)")
        else:
            cfg["resume"] = resume_step(cfg)
    elif not cfg.get("resume") and interactive():  # e.g. --dry-run in a terminal
        cfg["resume"] = resume_step(cfg)
    prof = load_profile(cfg)
    if guided:
        show_profile(prof)
        settings_step(cfg, prof, a)
    search = core.build_search(prof, cfg)
    if not search.roles:
        raise Quit("No role to search for. Use --role \"Job title\".")

    # Step 3 · Sources, with the live debit total
    if guided:
        ui.step(3, STEPS, "Job sources")
        if a.sources:
            ui.ok(f"Sources: {a.sources}  (from --sources)")
        else:
            sources_step(cfg, search, tok, acct)

    # Step 4 · Where to save the job links page (remembered for next time)
    if guided:
        ui.step(4, STEPS, "Where to save")
        if a.out:
            ui.ok(f"Saving to {output_dir(cfg)}  (from --out)")
        else:
            save_step(cfg)
        save_choices(cfg)
    else:
        show_profile(prof)

    prefs = core.build_prefs(prof, search, cfg)
    try:
        srcs = sources.resolve(cfg.get("sources"))
    except ValueError as e:
        raise Quit(str(e))

    if guided:
        console.print()
        console.print(Text.assemble((" REVIEW ", f"bold white on {BLUE}"), ("   Check the search before anything is spent", MUTED)))
        console.rule(style=BLUE, characters="─")
    console.print()
    if a.dry_run:
        budget = float(cfg.get("max_cost_usd") or 0) or None
        over = budget and sum(s.estimate(search) for s in srcs) > budget
        limited = f"your cap is {ui.money(budget)} per search (raise it with --budget)" if over else None
    else:
        tok, acct, budget, limited = budget_step(search, srcs, cfg, tok, acct, guided)
    planned = core.plan(search, srcs, budget)
    total = show_plan(search, prefs, planned)
    if limited:
        ui.warn(f"That's over the limit for this search: {limited}. Each source's spending limit is scaled down to fit, "
                "so some return fewer jobs.")

    if a.dry_run:
        say("\nDry run: nothing was sent to Apify. Actor inputs:")
        for p in planned:
            console.print(Text(f"\n# {p.source.key}  ->  {p.source.actor}  (cap {ui.money(p.cap_usd)})", style=f"bold {BLUE}"))
            say(json.dumps(p.input, indent=2, ensure_ascii=False))
        return

    if guided:
        console.print()
        if ui.select("Ready?", [(f"Run the search  ·  up to {ui.money(min(total, budget or total))}", ""),
                                ("Cancel", "Nothing is spent")], 0) == 1:
            raise Quit("Cancelled; nothing was spent.")

    out = output_dir(cfg)
    run_dir = out / "runs" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    console.print()
    console.print(Text.assemble((" RUNNING ", f"bold white on {BLUE}"), (f"   {len(planned)} actor(s) on Apify  ·  Ctrl+C stops and keeps what finished", MUTED)))
    console.rule(style=BLUE, characters="─")
    console.print()
    started = datetime.now()
    try:
        raw = run_actors(tok, planned, run_dir)
    except KeyboardInterrupt:
        raw = core.load_raw(run_dir / "raw")
        ui.warn("Stopped. Building the page from what finished.")
    cost = sum(r.get("cost", 0) for r in raw.values())
    meta = {"search": asdict(search), "sources": [p.source.key for p in planned], "started": started.isoformat(timespec="seconds"),
            "cost_usd": round(cost, 4), "errors": {k: r["error"] for k, r in raw.items() if r.get("error")},
            "config": {k: v for k, v in cfg.items() if not k.startswith("_") and k != "resume"}}
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    finish(raw, search, prof, prefs, run_dir, out, meta, a, acct)


def cmd_rescore(a):
    run_dir = Path(a.run_dir)
    if not (run_dir / "raw").is_dir():
        raise Quit(f"No raw results in {run_dir / 'raw'}")
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8")) if (run_dir / "run.json").is_file() else {}
    cfg = merge_args(load_config(a.config), a)
    if not cfg.get("resume") and interactive():
        cfg["resume"] = resume_step(cfg)
    prof = load_profile(cfg)
    show_profile(prof)
    saved = meta.get("search") or {}
    search = core.build_search(prof, cfg)
    if not a.role and saved.get("roles"):
        search.roles = saved["roles"]
    if not a.location:
        for k in ("location", "city", "country"):
            if saved.get(k) is not None:
                setattr(search, k, saved[k])
    if not a.posted and saved.get("hours"):
        search.hours = saved["hours"]
    prefs = core.build_prefs(prof, search, cfg)
    raw = core.load_raw(run_dir / "raw")
    say(f"\nRe-scoring {sum(len(r.get('items') or []) for r in raw.values())} saved rows from {run_dir} (no Apify credits used)")
    finish(raw, search, prof, prefs, run_dir, output_dir(cfg), meta, a)


def finish(raw, search, prof, prefs, run_dir, out, meta, a, acct=None):
    jobs, stats = core.collect(raw, search, prof, prefs, sources.BY_KEY)
    labels = list(dict.fromkeys(j["source_label"] for j in jobs)) or [sources.BY_KEY[k].label for k in raw if k in sources.BY_KEY]
    page, n = report.write_all(jobs, run_dir, sources_used=labels, hours=search.hours, profile=prof, meta=meta)
    out.mkdir(parents=True, exist_ok=True)
    latest = (out / "job_links.html").resolve()
    shutil.copyfile(page, latest)

    count = lambda c: sum(1 for j in jobs if j["relevant"] and j["chance"] == c)
    off = sum(1 for j in jobs if not j["relevant"])
    console.print()
    console.print(Text.assemble((" RESULTS ", f"bold white on {GREEN}"), ("   Your ranked job links are ready", MUTED)))
    console.rule(style=GREEN, characters="─")
    console.print()
    console.print(Text.assemble(("  ", ""), (f" High {count('High')} ", f"bold white on {GREEN}"), ("   ", ""),
                                (f" Medium {count('Medium')} ", "bold black on #FBBC05"), ("   ", ""),
                                (f" Low {count('Low')} ", f"bold white on {RED}"), ("    chance of an interview", MUTED)))
    console.print()
    console.print(Text(f"  {stats['rows']} jobs fetched  ·  {stats['stale']} too old  ·  {stats['duplicates']} duplicates  ·  "
                       f"{stats['unreadable']} unreadable  ·  {off} outside your field", style=MUTED))
    for key, r in raw.items():
        if r.get("error"):
            ui.warn(f"{key}: {r['error']}")
    if meta.get("cost_usd") is not None:
        line = Text.assemble(("  Cost about ", ""), (ui.money(meta["cost_usd"]), "bold #F29900"), (" this search", ""))
        if acct and acct.get("left") is not None:
            line.append_text(Text.assemble(("   ·   credit left about ", MUTED), (ui.money(max(0.0, acct["left"] - meta["cost_usd"])), f"bold {GREEN}")))
        console.print(line)
    top = [j for j in jobs if j["relevant"] and j["chance"] in ("High", "Medium")][:8]
    if top:
        t = ui.table(("fit", "right"), "chance", "title", "company", "source", title="Top matches")
        for j in top:
            c = GREEN if j["chance"] == "High" else "#F29900"
            t.add_row(Text(str(j["score"]), style=f"bold {c}"), Text(j["chance"], style=c), j["title"][:52], j["company"][:28], j["source_label"])
        console.print()
        console.print(ui.indent(t))
    console.print()
    console.print(Text.assemble(("  Saved   ", f"bold {BLUE}"), ui.link(latest.as_uri(), str(latest), GREEN), (f"   ({n} jobs)", MUTED)))
    console.print(Text.assemble(("  Run     ", f"bold {BLUE}"), (str(run_dir.resolve()), ""), ("   (jobs.csv, jobs.json, raw)", MUTED)))
    console.print()
    want_open = getattr(a, "open", False)
    if not want_open and interactive() and not getattr(a, "yes", False):
        choice = ui.select("What next?", [("Open the job links page in my browser", ""), ("Open the folder", str(out)), ("Done", "")], 0)
        if choice == 1:
            ui.open_path(out)
        want_open = choice == 0
    if want_open:
        webbrowser.open(latest.as_uri())
    ui.credit_footer()


# ---------------------------------------------------------------- argparse
def add_search_args(p):
    p.add_argument("--resume", help="resume file (PDF, DOCX, TXT, MD); skips the file window")
    p.add_argument("--role", action="append", help="job title to search; repeat for more (default: title on your resume)")
    p.add_argument("--location", help="where to search, e.g. India, Hyderabad, Remote (default: your country)")
    p.add_argument("--prefer", action="append", help="a city you'd work in (scores higher); repeat for more")
    p.add_argument("--min-match", type=int, help="leave out jobs whose resume match is below this (default 40)")
    p.add_argument("--config", help="config file (default: ./config.json)")
    p.add_argument("--out", help="folder for the job links page (default: Downloads/JobSearch, or the folder chosen last time)")
    p.add_argument("--open", action="store_true", help="open the page in your browser when done")


def build_parser():
    p = argparse.ArgumentParser(prog="python -m jobsearch", description="Find fresh jobs with Apify and rank them against your resume.",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("\n\n", 1)[1])
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("search", help="search, score and write job_links.html (the default)")
    for target in (p, s):
        add_search_args(target)
        target.add_argument("--sources", help="comma-separated sources, skipping the menu ('all' = all but career-sites)")
        target.add_argument("--per-source", type=int, help="max jobs per source, i.e. what you pay for (default 25)")
        target.add_argument("--posted", help="only jobs posted within: 24h (default), 3d, 7d, 30d")
        target.add_argument("--budget", type=float, help="spending cap per search in USD (default 0.50)")
        target.add_argument("--remote-only", action="store_true", help="remote jobs only, where the board supports it")
        target.add_argument("--only-new", action="store_true", help="ask actors for jobs new since your last run (cheaper on repeat runs)")
        target.add_argument("--dry-run", action="store_true", help="show the plan and cost estimate; spend nothing, no key needed")
        target.add_argument("-y", "--yes", action="store_true", help="no menus: use config.json, --resume and APIFY_TOKEN")
    c = sub.add_parser("credits", help="credit left, cost per source, and what each source has used this month")
    c.add_argument("--config")
    c.add_argument("--per-source", type=int)
    sub.add_parser("change-key", help="save a different Apify API key as APIFY_TOKEN")
    sub.add_parser("forget-key", help="remove the APIFY_TOKEN environment variable")
    pr = sub.add_parser("profile", help="show what was read from your resume")
    add_search_args(pr)
    sub.add_parser("sources", help="list sources, actors and prices (offline)")
    i = sub.add_parser("init", help="create config.json step by step")
    i.add_argument("--config")
    r = sub.add_parser("rescore", help="re-score a saved run with your current resume/config (free)")
    r.add_argument("run_dir")
    add_search_args(r)
    r.add_argument("--posted")
    return p


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    a = build_parser().parse_args(argv)
    commands = {"sources": cmd_sources, "profile": cmd_profile, "init": cmd_init, "rescore": cmd_rescore, "credits": cmd_credits,
                "change-key": cmd_change_key, "forget-key": cmd_forget_key}
    try:
        commands.get(a.cmd, cmd_search)(a)
    except Quit as e:
        console.print()
        console.print(Text(f"  {e}", style=f"bold {YELLOW}"))
        return 1
    except (KeyboardInterrupt, ui.Cancelled):
        console.print(Text("\n  Stopped. Nothing more was spent.", style=f"bold {YELLOW}"))
        return 130
    return 0
