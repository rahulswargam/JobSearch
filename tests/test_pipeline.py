"""Offline tests: never call Apify. Run with  python -m unittest discover tests  (or python tests/test_pipeline.py)."""
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jobsearch import apify, cli, core, normalize as nz, report, resume, skills, sources  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
RESUME = FIX / "resume_devops.txt"


def load_samples():
    """samples.json with its relative time placeholders filled in."""
    now = datetime.now(timezone.utc)
    ist = timezone(timedelta(hours=5, minutes=30))

    def fill(v):
        if isinstance(v, str):
            m = re.fullmatch(r"\{(h|d|ist):(\d+)\}", v)
            if m:
                kind, n = m.group(1), int(m.group(2))
                if kind == "h":
                    return (now - timedelta(hours=n)).isoformat().replace("+00:00", "Z")
                if kind == "d":
                    return (now - timedelta(days=n)).date().isoformat()
                return (now - timedelta(hours=n)).astimezone(ist).strftime("%Y-%m-%d %H:%M:%S")
            return v
        if isinstance(v, list):
            return [fill(x) for x in v]
        if isinstance(v, dict):
            return {k: fill(x) for k, x in v.items()}
        return v

    data = json.loads((FIX / "samples.json").read_text(encoding="utf-8"))
    return {k: fill(v) for k, v in data.items() if not k.startswith("_")}


def setup(cfg=None):
    cfg = cfg or {"location": "India", "preferred_locations": ["Bengaluru"], "posted_within_hours": 24}
    prof = resume.build_profile(RESUME)
    search = core.build_search(prof, cfg)
    prefs = core.build_prefs(prof, search, cfg)
    return prof, search, prefs


class ResumeTests(unittest.TestCase):
    def test_reads_profile(self):
        p = resume.build_profile(RESUME)
        self.assertEqual(p.title, "Site Reliability Engineer")
        self.assertEqual(p.family, "devops")
        self.assertEqual((p.years_total, p.years_relevant), (6.0, 4.0))
        self.assertEqual((p.city, p.country), ("Pune", "India"))
        for s in ("Kubernetes", "Terraform", "AWS", "Go", "Prometheus", "EKS", "CI/CD", "GitHub Actions"):
            self.assertIn(s, p.skills)
        self.assertNotIn("Java", p.skills)

    def test_overrides_win(self):
        p = resume.build_profile(RESUME, {"years_total": 9, "title": "Platform Engineer", "extra_skills": ["Pulumi"], "ignore_skills": ["Azure"]})
        self.assertEqual((p.years_total, p.title), (9, "Platform Engineer"))
        self.assertIn("Pulumi", p.skills)
        self.assertNotIn("Azure", p.skills)

    def test_dates_fallback(self):
        total, rel = resume.years_from_dates(RESUME.read_text(encoding="utf-8"), "devops")
        self.assertGreater(total, 6)  # Jun 2019 to now, education range ignored
        self.assertLess(total, 30)


class ParserTests(unittest.TestCase):
    def test_years(self):
        self.assertEqual(nz.parse_years("3-5 Yrs"), (3, 5))
        self.assertEqual(nz.parse_years("5+ years"), (5, None))
        self.assertEqual(nz.parse_years("4–8 yrs"), (4, 8))
        self.assertEqual(nz.parse_years({"min": 5, "max": None, "text": "x"}), (5, None))
        self.assertEqual(nz.years_in_text("You need 5+ years of DevOps experience."), (5, None))

    def test_applicants(self):
        self.assertEqual(nz.applicants_label({"min": 200, "max": None, "text": "Over 200 applicants"}), "200+")
        self.assertEqual(nz.applicants_label("Be among the first 25 applicants"), "Under 25")
        self.assertEqual(nz.applicants_label(145), "145")

    def test_dates(self):
        dt, has_time = nz.parse_date("2026-01-22 13:23:19", 5.5)
        self.assertEqual((dt.hour, dt.minute, has_time), (7, 53, True))
        dt, has_time = nz.parse_date("Posted 3 hours ago")
        self.assertTrue(has_time and nz.within(dt, has_time, 24))
        dt, has_time = nz.parse_date("2020-01-01")
        self.assertFalse(nz.within(dt, has_time, 24))

    def test_skills(self):
        self.assertEqual(skills.canonical("k8s"), "Kubernetes")
        self.assertIn("CI/CD", skills.find_in_text("Build ci/cd pipelines"))
        self.assertNotIn("Go", skills.find_in_text("Go ahead and apply"))  # tag-only
        self.assertIn("Go", skills.from_tags(["golang"]))

    def test_clean_url(self):
        self.assertEqual(nz.clean_url("https://x.com/j?id=1&utm_source=li"), "https://x.com/j?id=1")


class SourceTests(unittest.TestCase):
    def test_every_source_normalizes_its_sample(self):
        prof, search, prefs = setup()
        samples = load_samples()
        self.assertEqual(set(samples), set(sources.BY_KEY), "samples.json should cover every source")
        for key, items in samples.items():
            src = sources.BY_KEY[key]
            for it in items:
                j = src.normalize(it, search)
                self.assertIsNotNone(j, key)
                self.assertTrue(j["title"] and j["url"].startswith("http"), key)
                self.assertIn(j["kind"], ("company", "easy", "board"), key)

    def test_company_links(self):
        prof, search, _ = setup()
        s = load_samples()
        li = sources.BY_KEY["linkedin"].normalize(s["linkedin"][0], search)
        self.assertEqual((li["kind"], li["link"]), ("company", "https://careers.avaloq.com/job/123?ref=li"))
        easy = sources.BY_KEY["linkedin"].normalize(s["linkedin"][1], search)
        self.assertEqual((easy["kind"], easy["applicants"]), ("easy", "200+"))
        nk = sources.BY_KEY["naukri"].normalize(s["naukri"][1], search)
        self.assertTrue(nk["link"].startswith("https://career.infosys.com"))
        self.assertEqual(sources.BY_KEY["naukri"].normalize(s["naukri"][0], search)["kind"], "easy")

    def test_inputs_build_for_every_source(self):
        prof, search, _ = setup()
        for src in sources.ALL:
            inp = src.build_input(search)
            self.assertIsInstance(inp, dict, src.key)
            json.dumps(inp)

    def test_freshness_and_limits_in_inputs(self):
        _, search, _ = setup()
        self.assertEqual(sources.BY_KEY["linkedin"].build_input(search)["timePostedRange"], "86400")
        self.assertEqual(sources.BY_KEY["naukri"].build_input(search)["freshness"], 1)
        self.assertEqual(sources.BY_KEY["naukri"].build_input(search)["maxResults"], 25)
        self.assertNotIn("location", sources.BY_KEY["naukri"].build_input(search))  # "India" = everywhere
        search.roles = ["DevOps Engineer", "SRE"]
        li = sources.BY_KEY["linkedin"].build_input(search)
        self.assertEqual(len(li["searchUrls"]), 2)
        self.assertIn("f_TPR=r86400", li["searchUrls"][0])

    def test_resolve(self):
        self.assertEqual([s.key for s in sources.resolve("linkedin, naukri")], ["linkedin", "naukri"])
        self.assertNotIn("career-sites", [s.key for s in sources.resolve(["all"])])
        with self.assertRaises(ValueError):
            sources.resolve("monster")


class PipelineTests(unittest.TestCase):
    def collect(self):
        prof, search, prefs = setup()
        raw = {k: {"items": v} for k, v in load_samples().items()}
        return core.collect(raw, search, prof, prefs, sources.BY_KEY)

    def test_collect(self):
        jobs, stats = self.collect()
        titles = [j["title"] for j in jobs]
        self.assertEqual(stats["stale"], 1)  # the 9-day-old LinkedIn job
        self.assertNotIn("Senior Site Reliability Engineer", titles)
        self.assertEqual(stats["duplicates"], 1)  # Accenture on Naukri and Foundit
        acc = [j for j in jobs if j["company"] == "Accenture"]
        self.assertEqual(len(acc), 1)
        self.assertTrue(acc[0]["link"])  # the copy with the company's own link is kept
        java = next(j for j in jobs if "Java" in j["title"])
        self.assertFalse(java["relevant"])
        devops = next(j for j in jobs if j["company"] == "Avaloq")
        self.assertTrue(devops["relevant"])
        self.assertGreater(devops["score"], java["score"])
        self.assertEqual(jobs, sorted(jobs, key=lambda j: (-j["score"], -j["match"])))

    def test_scoring_notes(self):
        jobs, _ = self.collect()
        lead = next(j for j in jobs if j["title"] == "DevOps Lead")
        self.assertIn("Asks 8", lead["why"])
        self.assertIn(lead["chance"], ("Low", "Medium"))
        pune = next(j for j in jobs if j["company"] == "Avaloq")
        self.assertIn("no relocation", pune["why"])
        self.assertIn("you meet it", pune["why"])

    def test_plan_budget(self):
        _, search, _ = setup()
        rows = core.plan(search, sources.resolve("linkedin,naukri"), budget=0.05)
        self.assertLessEqual(sum(r.cap_usd for r in rows), 0.05 + 1e-9)
        self.assertEqual(rows[0].max_items, 25)
        cs = core.plan(search, [sources.BY_KEY["career-sites"]])[0]
        self.assertEqual(cs.max_items, 200)

    def test_report(self):
        jobs, _ = self.collect()
        prof, search, _ = setup()
        with tempfile.TemporaryDirectory() as d:
            page, n = report.write_all(jobs, d, sources_used=["LinkedIn", "Naukri"], hours=24, profile=prof)
            html = page.read_text(encoding="utf-8")
            self.assertNotIn("/*DATA*/{}", html)
            data = json.loads(re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1).replace("<\\/", "</"))
            self.assertEqual(len(data["jobs"]), n)
            self.assertTrue(all(j["chance"] in ("High", "Medium") for j in data["jobs"]))
            self.assertEqual([j["rank"] for j in data["jobs"]], list(range(1, n + 1)))
            self.assertTrue((Path(d) / "jobs.csv").read_text(encoding="utf-8-sig").startswith("Overall Fit"))


class ApifyClientTests(unittest.TestCase):
    def test_run_flow_and_caps(self):
        calls = []

        class Fake(apify.Apify):
            def _req(self, method, path, params=None, body=None, timeout=None):
                calls.append((method, path, params))
                if path.endswith("/runs"):
                    return {"data": {"id": "r1", "status": "RUNNING"}}
                if path.startswith("/actor-runs/"):
                    return {"data": {"id": "r1", "status": "SUCCEEDED", "defaultDatasetId": "d1",
                                     "chargedEventCounts": {"apify-default-dataset-item": 2},
                                     "pricingInfo": {"pricingPerEvent": {"actorChargeEvents": {"apify-default-dataset-item": {"eventPriceUsd": 0.001}}}}}}
                if path.startswith("/datasets/"):
                    return [{"a": 1}, {"a": 2}]
                raise AssertionError(path)

        items, run = Fake("tok").run("user/actor", {"q": 1}, max_items=25, max_charge_usd=0.05)
        self.assertEqual(len(items), 2)
        self.assertEqual(calls[0][1], "/acts/user~actor/runs")
        self.assertEqual(calls[0][2], {"maxItems": 25, "maxTotalChargeUsd": "0.0500", "timeout": 600})
        self.assertAlmostEqual(apify.run_cost(run), 0.002)


class CliTests(unittest.TestCase):
    def test_dry_run_spends_nothing(self):
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as d, redirect_stdout(buf):
            code = cli.main(["--resume", str(RESUME), "--dry-run", "--sources", "linkedin,naukri", "--out", d])
        out = buf.getvalue()
        self.assertEqual(code, 0, out)
        self.assertIn("Dry run: nothing was sent to Apify", out)
        self.assertIn('"timePostedRange": "86400"', out)

    def test_rescore_from_saved_raw(self):
        samples = load_samples()
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "runs" / "r1"
            (run / "raw").mkdir(parents=True)
            for k, v in samples.items():
                (run / "raw" / f"{k}.json").write_text(json.dumps({"items": v}), encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["rescore", str(run), "--resume", str(RESUME), "--out", d])
            self.assertEqual(code, 0, buf.getvalue())
            self.assertTrue((Path(d) / "job_links.html").is_file())
            self.assertIn("no Apify credits used", buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
