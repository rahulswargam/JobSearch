# Job Search

**Built by [Rahul Swargam](https://rahulswargam.online/)** · Visit [rahulswargam.online](https://rahulswargam.online/)

Finds jobs posted in the last 24 hours on LinkedIn, Naukri and 12 other job boards using Apify actors. It scores each job against your resume and writes `job_links.html`: one big apply button per job, High chance first, then Medium. Low-chance and off-field roles are left out.

It runs on its own: no AI service, no browser automation, no LinkedIn login. Everyone uses their own Apify account and API key.

## Setup

1. Python 3.10 or newer.
2. `pip install -r requirements.txt` (rich, prompt_toolkit, pypdf).
3. An Apify account. The free plan includes $5 of credit a month. Your API key is at <https://console.apify.com/settings/integrations>.

## Running a search

```
python -m jobsearch
```

Or double-click `run.bat`. It's a colourful guided run in three steps. You move with the arrow keys, and nothing is spent until you choose **Run the search**.

1. **Apify API key.** It first looks for a key in the `APIFY_TOKEN` environment variable. If one is found, it shows the account and credit left, and you can use it or switch to a different key (for example another account that still has credit). If none is found, it shows a clickable link to the Apify key page, offers to open it in your browser, and then takes your key with hidden input.
2. **Your resume.** A file window opens to pick your resume (PDF, Word or text). It shows what it read (role, years of experience, city, skills) and what it will search for. You can accept that or change the role, location and cities.
3. **Job sources.** A list of all 14 actors with checkboxes. Space ticks a source, A ticks all, N clears. The line under the list updates as you tick, with how much will be debited and the credit you'll have left. Each row shows the most a run can cost, how many runs your credit covers, and what that actor used this month.

Then it shows the plan (each actor, how many jobs it may return, the most it can cost). If the total is over your per-search cap, it asks whether to raise the cap. If it's over the credit you have left, it offers to switch to another Apify account. Then **Run the search**: a live table shows each actor running. At the end you get the results, the top matches, and an offer to open the page.

`--dry-run` shows the plan and the most it can cost without a key and without spending anything.

## Your key and resume are never stored

This repo is public, so nothing personal is written by the tool:

- **API key:** it's kept in memory for the current run only. It's never written to disk, `config.json`, the output, or logs. To skip typing it each time, set it yourself as an environment variable (see below).
- **Resume:** it's chosen in the file window each run, or with `--resume`, and only read. It's never copied, and its path isn't saved.
- `config.json` (your search settings) and `output/` are in `.gitignore`. So are `*.pdf`, `*.docx` and `.env` files, so a resume or key can't be committed by accident.

To skip typing the key, set it as an environment variable, which lives outside this repo:

| Shell | Command |
|---|---|
| Windows (permanent) | `setx APIFY_TOKEN "your-key"`, then open a new terminal |
| PowerShell (this window only) | `$env:APIFY_TOKEN = "your-key"` |
| macOS / Linux | `export APIFY_TOKEN=your-key` (add it to `~/.bashrc` or `~/.zshrc`) |

## The source list and your credit

Apify credit is one balance for your whole account; it isn't split per actor. For each actor the list shows:

- **per run**: the most one search can cost with that actor (for 25 jobs by default).
- **runs left**: how many such searches your remaining credit covers.
- **used this month**: how many times you ran that actor this billing cycle and what Apify recorded for those runs.

`python -m jobsearch credits` shows the same table without running a search.

## Use Google Sans in the terminal (optional)

A program can't choose the terminal's font; the terminal app does. Google publishes a monospaced version of Google Sans, **Google Sans Code**, on [Google Fonts](https://fonts.google.com/specimen/Google+Sans+Code). To use it:

1. Download it from Google Fonts and install the font files (right-click → Install).
2. In Windows Terminal, open Settings → your profile (PowerShell or Command Prompt) → Appearance → Font face, and choose **Google Sans Code**.

For true colours, use Windows Terminal (the default terminal in Windows 11), VS Code's terminal, iTerm2, or any modern terminal. Ctrl+click opens the links.

## What you get

| File | What it is |
|---|---|
| `output/job_links.html` | The latest apply-links page. Open this one. |
| `output/runs/<date_time>/job_links.html` | That run's page |
| `output/runs/<date_time>/jobs.csv` | Every job with all scores, including Low; opens in Excel |
| `output/runs/<date_time>/jobs.json` | Same data as JSON |
| `output/runs/<date_time>/raw/` | What each actor returned, kept so you can re-score without paying again |

On the page, the button goes straight to the company's careers site when the job board gives that link. Otherwise it opens the board (Easy Apply on LinkedIn, Apply on Naukri, and so on). Each card shows the skills you match, a few to brush up (`+ Azure`), and why the chance is what it is. You can filter by chance, by where you apply, and by source, or search. "Mark applied" is saved in your browser and carries over to the next day's page.

## Sources

| Key | Board | Actor | Max cost, 25 jobs* | Notes |
|---|---|---|---|---|
| `linkedin` | LinkedIn | crawlworks/linkedin-jobs-scraper | $0.125 | Applicant counts, Easy Apply vs company link |
| `naukri` | Naukri | blackfalcondata/naukri-jobs-feed | $0.011 | Cheapest; full details and company apply link |
| `naukri-memo23` | Naukri | memo23/naukri-scraper | $0.021 | Employer's own apply link |
| `naukri-mk` | Naukri | muhammetakkurtt/naukri-job-scraper | $0.038 | Basic rows, one role per run |
| `india-feed` | Naukri, Foundit, Indeed, LinkedIn, Shine, Hirist | getascraper/india-job-inventory-feed | $0.050 | Six boards in one run |
| `instahyre` | Instahyre | getascraper/instahyre-jobs-scraper | $0.026 | No posting dates |
| `instahyre-memo23` | Instahyre | memo23/instahyre-jobs-scraper | $0.038 | External apply links |
| `hirist` | Hirist.tech | logiover/hirist-tech-scraper | $0.075 | No date filter: may bill older jobs |
| `wellfound` | Wellfound | blackfalcondata/wellfound-scraper | $0.080 | Startups, salary and equity |
| `remote` | Company career pages | hirebase/remote-jobs | $0.126 | Remote only, direct apply links |
| `weworkremotely` | We Work Remotely | inlifeprojects/weworkremotely-jobs-scraper | $0.025 | No date filter: may bill older jobs |
| `career-sites` | 275k company career sites | fantastic-jobs/career-site-job-listing-feed | $0.600 | 200 jobs minimum per run; mostly older jobs; not in `all` |
| `upwork` | Upwork | blackfalcondata/upwork-scraper | $0.026 | Freelance |
| `upwork-neatrat` | Upwork | neatrat/upwork-job-scraper | $0.175 | Freelance, one page of 10, 20 or 50 |

\* Free-plan prices taken from Apify in November 2026. Paid plans cost less, and actors can change their prices.

## How it keeps Apify costs down

- **Fresh jobs only.** Each actor's own date filter is set to your window (24h by default). Anything older that still comes back is dropped before scoring.
- **Small caps.** 25 jobs per source by default (`--per-source`).
- **Filters run on Apify's side.** Your role, your location and your years of experience are sent to the actor, so it skips jobs that don't fit before you're billed for them.
- **No paid extras.** Emails, company enrichment and detail pages that cost extra are all left off.
- **Hard spending limit.** Each run is started with Apify's `maxTotalChargeUsd` and `maxItems`, so it can't go past its cap. All caps together stay under `max_cost_usd` (default $0.50 per search, which the guided run offers to raise) and never above the credit you have left.
- **Re-score for free.** `python -m jobsearch rescore output/runs/<date_time>` re-scores saved results after you change your resume or settings, with no new Apify runs.
- **`--only-new`** asks actors that support it for jobs added since your last run, so repeat runs on the same day cost almost nothing.

## How jobs are scored

- **Resume match (0–100):** the share of the job's skills that you have (skills in the job title count double), plus how close the job title is to your role.
- **Interview likelihood (0–100):** experience asked vs yours (it reads "5 years total, 3+ in DevOps" from a resume), applicant count, whether the job is in your city or your preferred cities, and senior or junior titles.
- **Overall fit** = 0.55 × match + 0.45 × likelihood. The page is sorted by this.
- **Chance:** High when likelihood is 65 or more, Medium from 45 to 64, Low below 45. A job with a resume match under `min_match` (40) is treated as outside your field and left out.

If the tool misreads your resume (`python -m jobsearch profile` shows what it found), fix it in `config.json` → `profile`: `years_total`, `years_relevant`, `title`, `city`, `extra_skills`, `ignore_skills`.

## Options

| Option | What it does |
|---|---|
| `--resume PATH` | Resume file (PDF, DOCX, TXT, MD); skips the file window |
| `--role "Title"` | Role to search for; repeat for more |
| `--location India` | Where to search. A country covers all of it; `Remote` searches remote jobs |
| `--prefer City` | A city you'd work in (scores higher); repeat for more |
| `--sources a,b` | Which sources, skipping the checkbox list (`all` = all but `career-sites`) |
| `--per-source 25` | Max jobs per source, which is what you pay for |
| `--posted 24h` | Freshness window: `24h`, `3d`, `7d`, `30d` |
| `--budget 0.5` | Spending cap per search, in USD |
| `--min-match 40` | Leave out jobs below this resume match |
| `--remote-only` | Remote jobs only, where the board supports it |
| `--only-new` | Only jobs new since your last run (for actors that support it) |
| `--dry-run` | Show the plan and actor inputs; spend nothing, no key needed |
| `-y` | No menus: uses `config.json`, `--resume` and `APIFY_TOKEN` (for scheduled runs) |
| `--open` | Open the page when done |

Other commands: `credits`, `init`, `profile`, `sources`, `rescore <run folder>`.

## Run it every morning (optional)

Set `APIFY_TOKEN` with `setx`. Then create a Windows Task Scheduler task that runs `python` with these arguments, with "start in" set to this folder:

```
-m jobsearch -y --resume "C:\path\to\resume.pdf"
```

## For the web app later

The pipeline doesn't depend on the command line. A web backend can call the same functions with the key each user enters in a form, held for that request only:

```python
from jobsearch import core, report, resume, sources
profile = resume.build_profile("upload.pdf")
search  = core.build_search(profile, settings)       # settings: same keys as config.json
prefs   = core.build_prefs(profile, search, settings)
planned = core.plan(search, sources.resolve(settings["sources"]), budget=0.5)
raw     = core.fetch(user_token, planned)
jobs, _ = core.collect(raw, search, profile, prefs, sources.BY_KEY)
html, cards = report.render(jobs, sources_used=["LinkedIn", "Naukri"], hours=search.hours, profile=profile)
```

## Adding an actor

Each actor is a small class in `jobsearch/sources.py`. `build_input()` turns the search into the actor's input, and `normalize()` turns one result row into a job. Add the class to `ALL` and its Apify ID to `ACTOR_IDS`, add a sample row to `tests/fixtures/samples.json`, and run the tests.

## Tests

```
python -m unittest discover -s tests -v
```

The tests run offline and never call Apify. They cover:

- resume reading, every actor's output format, scoring and de-duplication
- the cost caps and the page
- the guided run with a fake Apify account: key scan and switching accounts, the resume file window, ticking sources, budget and credit checks
- the real arrow-key menus, driven with simulated keystrokes

## Project layout

| Path | What it is |
|---|---|
| `jobsearch/cli.py` | Commands and the guided steps |
| `jobsearch/ui.py` | Colours, banner, arrow-key menus, checkboxes, file window |
| `jobsearch/core.py` | Pipeline: plan, run actors, collect, de-duplicate |
| `jobsearch/sources.py` | One adapter per Apify actor |
| `jobsearch/apify.py` | Small Apify API client with spending caps |
| `jobsearch/resume.py` | Reads the resume: role, years, skills, city |
| `jobsearch/scoring.py` | Match, likelihood, overall fit, chance |
| `jobsearch/skills.py`, `roles.py` | Skill dictionary, role families, cities |
| `jobsearch/report.py`, `templates/` | The apply-links page, CSV and JSON |

---

Built by **Rahul Swargam** · [rahulswargam.online](https://rahulswargam.online/)
