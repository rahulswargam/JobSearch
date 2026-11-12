# Job Search

**Built by Rahul Swargam** · [Visit my website ↗](https://rahulswargam.online/)

Finds jobs posted in the last 24 hours on LinkedIn, Naukri and 12 other job boards using Apify actors. It scores each job against your resume and writes `job_links.html`: one big apply button per job, High chance first, then Medium. Low-chance and off-field roles are left out.

It runs on its own: no AI service, no browser automation, no LinkedIn login. Everyone uses their own Apify account and API key.

## Setup (Windows and macOS)

One file per system installs everything Job Search needs, always at the **latest version**, then checks that it works. Run it again any time to update everything.

| | Windows 10 / 11 | macOS (Apple Silicon or Intel) |
|---|---|---|
| One-click setup | Double-click **`setup-windows.bat`** | In Terminal, in this folder: **`bash setup-mac.sh`** |
| Preview only, no changes | `setup-windows.bat /check` | `bash setup-mac.sh --check` |
| No questions | `setup-windows.bat /yes` | `bash setup-mac.sh --yes` |

What they install:

| Tool | What it's for | Windows | macOS |
|---|---|---|---|
| Package manager | installs and updates everything below | winget (built in) | Homebrew (installed if missing) |
| Python 3 (newest) | runs the tool, with pip and venv | Python 3.x from python.org via winget | `python@3.x` from Homebrew |
| Tkinter | the resume file window and the save-folder window | included with Python | `python-tk@3.x` |
| rich | colours, tables, live progress | in `.venv` | in `.venv` |
| prompt_toolkit | arrow-key menus and checkboxes | in `.venv` | in `.venv` |
| pypdf | reads PDF resumes | in `.venv` | in `.venv` |
| certifi | up-to-date HTTPS certificates for the Apify API | in `.venv` | in `.venv` |
| PyMuPDF (optional) | better text from some PDF resumes | in `.venv` | in `.venv` |
| keyring (optional) | moves a key saved by an older version | in `.venv` | in `.venv` |
| Git | downloads and updates this project | Git for Windows | `git` |
| Terminal | full colours and clickable links | Windows Terminal | Terminal (built in) |
| Google Sans Code | the terminal font | installed for your account and set in Windows Terminal (as "Google Sans Code Monospace") | Homebrew font; choose it in Terminal → Settings → Profiles → Text |
| Web browser | opens the job links page | your default (Edge is built in) | your default (Safari is built in) |
| Apify account | runs the job searches | free at [console.apify.com](https://console.apify.com); the first run asks for its API key | same |

The Python packages go into a `.venv` folder inside this project (ignored by Git), so they never clash with other Python projects. `run.bat` and `run.command` use it automatically.

## Running a search

| | Windows | macOS |
|---|---|---|
| Start | Double-click `run.bat`, or `.venv\Scripts\python -m jobsearch` | Double-click `run.command` (first time: right-click → Open), or `.venv/bin/python -m jobsearch` |

It's a colourful guided run in four steps. You move with the arrow keys, and nothing is spent until you choose **Run the search**.

1. **Apify API key.** It reads your key from the `APIFY_TOKEN` environment variable. If it finds one, it shows your account and the credit left. You choose **Continue with this key** or **Change API key** (for example, another account with credit left). If it doesn't find one, it says **No API key found** and offers to open the Apify key page in your browser. Paste the key once (it's hidden as you type) and it's saved as the `APIFY_TOKEN` environment variable, so you won't be asked again.
2. **Your resume.** If you've used a resume before, you get two choices:
   - **Use my previous resume**: shows the file name and when it was last changed. One key press, no file window.
   - **Use an updated resume**: a file window opens to pick a newer or different file (PDF, Word or text), which then becomes your saved resume.

   The first time, the file window opens straight away. Then it shows what it read (role, years of experience, city, skills) and what it will search for. You can accept that or change the role, location and cities.
3. **Job sources.** A list of all 14 actors with checkboxes. Space ticks a source, A ticks all, N clears. The line under the list updates as you tick, with how much will be debited and the credit you'll have left. Each row shows the most a run can cost, how many runs your credit covers, and what that actor used this month.
4. **Where to save.** By default the page goes to `Downloads/JobSearch`. **Choose another folder** opens a folder window and fills in the path you pick, ready to confirm. Your choice is remembered for next time.

Then it shows the plan (each actor, how many jobs it may return, the most it can cost). If the total is over your per-search cap, it asks whether to raise the cap. If it's over the credit you have left, it offers **Change API key**. Then **Run the search**: a live table shows each actor running. At the end you get the results and the top matches, with options to open the page or its folder.

`--dry-run` shows the plan and the most it can cost without a key and without spending anything.

## Where your key and resume are remembered

Both are saved as **environment variables for your user account** and read back every run. This repo is public, so nothing personal is ever written into it.

| Variable | Holds | Set when | Remove with |
|---|---|---|---|
| `APIFY_TOKEN` | Your Apify API key | You paste a key (first run, or **Change API key**) | `python -m jobsearch forget-key` |
| `JOBSEARCH_RESUME` | Where your resume file is (its path; the file itself is never copied) | You choose a resume (first run, or **Use an updated resume**) | `python -m jobsearch forget-resume` |

- **API key:** pasted once and saved as `APIFY_TOKEN`. It's never written to this folder, `config.json`, the output, or logs.
  - **Windows:** user environment variables, the same as `setx`. You can see them in System Properties → Environment Variables → User variables.
  - **macOS / Linux:** `export` lines in your shell start-up file (`~/.zshrc`, `~/.bash_profile` or `~/.bashrc`), so every new terminal has them.
  - Replace the key with **Change API key** at the start of any run, or `python -m jobsearch change-key`.
- **Resume:** only its location is saved, in `JOBSEARCH_RESUME`, stored the same way as the key. The file stays where it is and is only read.
- `config.json` (your search settings and save folder) and `output/` are in `.gitignore`. So are `*.pdf`, `*.docx` and `.env` files, so a resume or key can't be committed by accident.

You can also set `APIFY_TOKEN` yourself (for example with `setx`); it's found the same way, even in a terminal that was already open before it was set.

## The source list and your credit

Apify credit is one balance for your whole account; it isn't split per actor. For each actor the list shows:

- **per run**: the most one search can cost with that actor (for 25 jobs by default).
- **runs left**: how many such searches your remaining credit covers.
- **used this month**: how many times you ran that actor this billing cycle and what Apify recorded for those runs.

`python -m jobsearch credits` shows the same table without running a search.

## Use Google Sans in the terminal (optional)

A program can't choose the terminal's font; the terminal app does. Google publishes a coding version of Google Sans, **Google Sans Code**, on [Google Fonts](https://fonts.google.com/specimen/Google+Sans+Code). The setup files install it, and on Windows they also set it in Windows Terminal. To do it by hand:

1. Download it from Google Fonts and install the font files (right-click → Install).
2. **Windows Terminal:** Settings → Defaults (or your profile) → Appearance → Font face → **Google Sans Code Monospace**. Use that exact name; plain "Google Sans Code" isn't found.
   **macOS Terminal:** Settings → Profiles → Text → Font → Change → **Google Sans Code**, style **Monospace**. In iTerm2: Settings → Profiles → Text → Font.

For the best colours, use Windows Terminal (the default in Windows 11), the macOS Terminal or iTerm2, or VS Code's terminal.

## What you get

In the folder you chose (`Downloads/JobSearch` by default):

| File | What it is |
|---|---|
| `job_links.html` | The latest apply-links page. Open this one. |
| `runs/<date_time>/job_links.html` | That run's page |
| `runs/<date_time>/jobs.csv` | Every job with all scores, including Low; opens in Excel |
| `runs/<date_time>/jobs.json` | Same data as JSON |
| `runs/<date_time>/raw/` | What each actor returned, kept so you can re-score without paying again |

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
- **Re-score for free.** `python -m jobsearch rescore <folder>/runs/<date_time>` re-scores saved results after you change your resume or settings, with no new Apify runs.
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
| `--resume PATH` | Resume file (PDF, DOCX, TXT, MD); default is the resume saved last time |
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
| `--out FOLDER` | Where to save the page, skipping step 4 |
| `-y` | No menus: uses the saved resume, `APIFY_TOKEN` and `config.json` (for scheduled runs) |
| `--open` | Open the page when done |

Other commands: `credits`, `change-key`, `forget-key`, `forget-resume`, `init`, `profile`, `sources`, `rescore <run folder>`.

## Run it every morning (optional)

Run one search by hand first, so your key, resume and save folder are remembered. Then create a Windows Task Scheduler task (or a macOS cron job) that runs Python with these arguments, starting in this folder:

```
-m jobsearch -y
```

## For the web app later

The pipeline doesn't depend on the command line. A web backend can call the same functions with the key each user enters:

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
- the guided run with a fake Apify account and stand-in environment variables: key found / saved once / changed, previous vs updated resume, ticking sources, the save folder, budget and credit checks
- saving the key and the resume path in a macOS shell start-up file (including paths with spaces), and moving a key saved by an older version
- the macOS file and folder windows (the AppleScript they run)
- the real arrow-key menus, driven with simulated keystrokes
- the setup files: they install every package the code uses and agree with `requirements.txt`

## Project layout

| Path | What it is |
|---|---|
| `jobsearch/cli.py` | Commands and the guided steps |
| `jobsearch/keystore.py` | Saves and reads `APIFY_TOKEN` and `JOBSEARCH_RESUME` as user environment variables (Windows + macOS) |
| `jobsearch/ui.py` | Colours, banner, arrow-key menus, checkboxes, file and folder windows (Windows + macOS) |
| `jobsearch/core.py` | Pipeline: plan, run actors, collect, de-duplicate |
| `jobsearch/sources.py` | One adapter per Apify actor |
| `jobsearch/apify.py` | Small Apify API client with spending caps |
| `jobsearch/resume.py` | Reads the resume: role, years, skills, city |
| `jobsearch/scoring.py` | Match, likelihood, overall fit, chance |
| `jobsearch/skills.py`, `roles.py` | Skill dictionary, role families, cities |
| `jobsearch/report.py`, `templates/` | The apply-links page, CSV and JSON |
| `setup-windows.bat`, `setup-mac.sh` | One-click setup: install or update every tool to the latest version |
| `jobsearch/setup_helper.py` | The setup files' helper: font, Terminal settings, PyPI versions, self-test |
| `run.bat`, `run.command` | Start a search |

---

Built by **Rahul Swargam** · [Visit my website ↗](https://rahulswargam.online/)
