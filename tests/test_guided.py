"""Offline tests for the guided run: key scan and switching, resume file window, ticking sources with the live
debit line, budget and credit checks. Menus are scripted and Apify is faked; nothing is sent anywhere."""
import io
import json
import os
import sys
import tempfile
import unittest
import webbrowser
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from jobsearch import apify, cli, core, sources, ui  # noqa: E402
from test_pipeline import RESUME, load_samples  # noqa: E402

KEY = "test-key-not-real-0001"
KEY2 = "test-key-not-real-0002"
LOW = "test-key-not-real-low"
ACCOUNTS = {
    KEY: {"username": "tester", "plan": "FREE", "used": 1.0, "limit": 5.0, "left": 4.0,
          "cycle_start": "2026-11-01T00:00:00.000Z", "cycle_end": "2026-12-01T00:00:00.000Z"},
    KEY2: {"username": "second", "plan": "FREE", "used": 2.0, "limit": 5.0, "left": 3.0, "cycle_start": None, "cycle_end": None},
    LOW: {"username": "almost-empty", "plan": "FREE", "used": 4.95, "limit": 5.0, "left": 0.05, "cycle_start": None, "cycle_end": None},
}
BY_ACTOR = {s.actor: s.key for s in sources.ALL}


class FakeApify:
    runs = []

    def __init__(self, token, timeout=60):
        self.token = token

    def account(self):
        if self.token not in ACCOUNTS:
            raise apify.ApifyError("Apify 401: rejected", status=401)
        return dict(ACCOUNTS[self.token])

    def usage_by_actor(self, since=None):
        return {sources.BY_KEY["linkedin"].actor_id: {"runs": 3, "usd": 0.31}}

    def run(self, actor, run_input, **kw):
        FakeApify.runs.append({"token": self.token, "actor": actor, "cap": kw.get("max_charge_usd")})
        return load_samples()[BY_ACTOR[actor]], {"id": "r1", "status": "SUCCEEDED", "defaultDatasetId": "d1"}


class Script:
    """Answers the menus in order. Each step is (kind, words expected in the question, answer)."""

    def __init__(self, steps):
        self.steps, self.asked, self.footer, self.rows = list(steps), [], "", []

    def take(self, kind, question):
        self.asked.append((kind, question))
        if not self.steps:
            raise AssertionError(f"unexpected {kind}: {question!r}")
        k, expect, answer = self.steps.pop(0)
        if k != kind or expect not in question:
            raise AssertionError(f"expected {k} {expect!r}, got {kind} {question!r}")
        return answer

    def select(self, question, options, default=0, answer_label=None):
        return self.take("select", question)

    def checkbox(self, question, columns, rows, selected, footer, min_selected=1, answer=None):
        keys = self.take("checkbox", question)
        self.rows, self.preselected = rows, set(selected)
        self.footer = "".join(t for _, t in footer(keys))
        return keys

    def secret(self, message):
        return self.take("secret", message)

    def pick_file(self, title="", initialdir=None):
        return self.take("file", title)

    def ask_text(self, message, default=""):
        return self.take("text", message)


class Guided(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.cwd = os.getcwd()
        os.chdir(self.dir)
        (self.dir / "config.json").write_text(json.dumps({"roles": ["Site Reliability Engineer"], "location": "India",
                                                          "preferred_locations": ["Pune"], "sources": ["linkedin", "naukri"]}), encoding="utf-8")
        FakeApify.runs = []
        self.opened = []
        env = {k: v for k, v in os.environ.items() if k not in cli.TOKEN_VARS}
        width = ui.console.width
        ui.console.width = 160
        self.addCleanup(setattr, ui.console, "width", width)
        for p in (mock.patch.dict(os.environ, env, clear=True), mock.patch.object(cli, "Apify", FakeApify),
                  mock.patch.object(core, "Apify", FakeApify), mock.patch.object(ui, "interactive", lambda: True),
                  mock.patch.object(webbrowser, "open", lambda url, *x, **k: self.opened.append(url))):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def run_cli(self, argv, steps):
        script = Script(steps)
        buf = io.StringIO()
        patches = [mock.patch.object(ui, name, getattr(script, name)) for name in ("select", "checkbox", "secret", "pick_file", "ask_text")]
        for p in patches:
            p.start()
        try:
            with redirect_stdout(buf):
                code = cli.main(argv)
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(script.steps, [], f"these menus never appeared: {script.steps}\n{buf.getvalue()}")
        return code, buf.getvalue(), script

    def files_text(self):
        return "".join(f.read_text(encoding="utf-8", errors="ignore") for f in self.dir.rglob("*") if f.is_file())

    def test_full_first_run(self):
        code, out, s = self.run_cli([], [
            ("select", "How do you want to continue?", 0),          # open the key page
            ("secret", "Paste your Apify API key", KEY),
            ("file", "Choose your resume", str(RESUME)),
            ("select", "Search settings", 0),
            ("checkbox", "Which job sources", ["linkedin", "naukri", "india-feed"]),
            ("select", "Ready?", 0),
            ("select", "Open the job links page now?", 0),
        ])
        self.assertEqual(code, 0, out)
        for expected in ("Built by", "Rahul Swargam", "rahulswargam.online", "STEP 1 OF 3", "STEP 2 OF 3", "STEP 3 OF 3",
                         "No Apify API key found", ui.APIFY_KEY_PAGE, "not saved anywhere", "Signed in to Apify as tester",
                         "$4.00 of $5.00 credit left", "Your resume", "RESULTS", "Top matches", "Job links page"):
            self.assertIn(expected, out)
        self.assertEqual(self.opened[0], ui.APIFY_KEY_PAGE)          # the key page was opened in the browser
        self.assertTrue(self.opened[-1].endswith("job_links.html"))  # and the result page at the end
        self.assertIn("up to $0.186 will be debited", s.footer)      # live total for the ticked sources
        self.assertIn("credit $4.00 → about $3.81", s.footer)
        self.assertEqual(s.preselected, {"linkedin", "naukri"})      # remembered from config.json
        self.assertEqual(sorted(BY_ACTOR[r["actor"]] for r in FakeApify.runs), ["india-feed", "linkedin", "naukri"])
        self.assertTrue((self.dir / "output" / "job_links.html").is_file())
        cfg = json.loads((self.dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["sources"], ["linkedin", "naukri", "india-feed"])
        self.assertNotIn("resume", cfg)                               # the resume is never stored
        self.assertNotIn(KEY, self.files_text())                      # nor the key, anywhere
        self.assertNotIn(KEY, out)
        self.assertNotIn(str(RESUME), (self.dir / "output").joinpath("runs").rglob("run.json").__next__().read_text(encoding="utf-8"))

    def test_env_key_found_then_switch_account(self):
        with mock.patch.dict(os.environ, {"APIFY_TOKEN": KEY}):
            code, out, _ = self.run_cli(["--resume", str(RESUME), "--sources", "naukri"], [
                ("select", "Which Apify key should this search use?", 1),
                ("select", "How do you want to continue?", 1),
                ("secret", "Paste your Apify API key", KEY2),
                ("select", "Search settings", 0),
                ("select", "Ready?", 0),
                ("select", "Open the job links page now?", 1),
            ])
        self.assertEqual(code, 0, out)
        self.assertIn("(key from APIFY_TOKEN)", out)
        self.assertIn("Signed in to Apify as second", out)
        self.assertEqual({r["token"] for r in FakeApify.runs}, {KEY2})

    def test_short_on_credit_switches_account_mid_way(self):
        with mock.patch.dict(os.environ, {"APIFY_TOKEN": LOW}):
            code, out, _ = self.run_cli(["--resume", str(RESUME), "--sources", "linkedin,naukri"], [
                ("select", "Which Apify key", 0),
                ("select", "Search settings", 0),
                ("select", "more than the $0.05 credit left", 0),     # switch to another account
                ("select", "How do you want to continue?", 1),
                ("secret", "Paste your Apify API key", KEY),
                ("select", "Ready?", 0),
                ("select", "Open the job links page now?", 1),
            ])
        self.assertEqual(code, 0, out)
        self.assertEqual({r["token"] for r in FakeApify.runs}, {KEY})

    def test_over_cap_can_raise_it(self):
        with mock.patch.dict(os.environ, {"APIFY_TOKEN": KEY}):
            code, out, _ = self.run_cli(["--resume", str(RESUME)], [
                ("select", "Which Apify key", 0),
                ("select", "Search settings", 0),
                ("checkbox", "Which job sources", ["linkedin", "remote", "wellfound", "hirist", "upwork-neatrat"]),
                ("select", "over your $0.50 per-search cap", 0),      # raise it for this search
                ("select", "Ready?", 0),
                ("select", "Open the job links page now?", 1),
            ])
        self.assertEqual(code, 0, out)
        total = sum(sources.BY_KEY[k].estimate(sources.Search(roles=["x"])) for k in ("linkedin", "remote", "wellfound", "hirist", "upwork-neatrat"))
        self.assertGreater(total, 0.5)
        self.assertGreaterEqual(sum(r["cap"] for r in FakeApify.runs), total)

    def test_resume_window_cancelled_then_typed(self):
        with mock.patch.dict(os.environ, {"APIFY_TOKEN": KEY}):
            code, out, _ = self.run_cli(["--sources", "naukri"], [
                ("select", "Which Apify key", 0),
                ("file", "Choose your resume", ""),
                ("select", "No file was chosen", 1),
                ("text", "Paste the full path", f'"{RESUME}"'),
                ("select", "Search settings", 0),
                ("select", "Ready?", 1),                                # cancel
            ])
        self.assertEqual(code, 1)
        self.assertIn("Cancelled; nothing was spent", out)
        self.assertEqual(FakeApify.runs, [])

    def test_rejected_keys(self):
        code, out, _ = self.run_cli(["--resume", str(RESUME), "--sources", "naukri"], [
            ("select", "How do you want to continue?", 1),
            ("secret", "Paste", "wrong-1"), ("secret", "Paste", "wrong-2"), ("secret", "Paste", "wrong-3"),
        ])
        self.assertEqual(code, 1)
        self.assertIn("Three keys were rejected", out)

    def test_scheduled_run_needs_env_key(self):
        with mock.patch.object(ui, "interactive", lambda: False):
            code, out, _ = self.run_cli(["--resume", str(RESUME), "-y"], [])
        self.assertEqual(code, 1)
        self.assertIn("APIFY_TOKEN", out)

    def test_credits_command(self):
        with mock.patch.dict(os.environ, {"APIFY_TOKEN": KEY}), mock.patch.object(ui, "interactive", lambda: False):
            code, out, _ = self.run_cli(["credits"], [])
        self.assertEqual(code, 0, out)
        self.assertIn("3 runs · $0.31", out)
        self.assertRegex(out, r"linkedin\s+crawlworks/linkedin-jobs-scraper\s+\$0\.125\s+31")


class Pieces(unittest.TestCase):
    def test_parse_picks(self):
        cur = ["linkedin", "naukri"]
        self.assertEqual(sources.parse_picks("", cur), cur)
        self.assertEqual(sources.parse_picks("1, 2 5", cur), ["linkedin", "naukri", "india-feed"])
        self.assertEqual(sources.parse_picks("2-4", cur), ["naukri", "naukri-memo23", "naukri-mk"])
        self.assertNotIn("career-sites", sources.parse_picks("all", cur))
        for bad in ("0", "99", "monster", "3-1"):
            with self.assertRaises(ValueError):
                sources.parse_picks(bad, cur)

    def test_every_source_has_an_actor_id(self):
        self.assertTrue(all(s.actor_id for s in sources.ALL))

    def test_clean_path(self):
        self.assertEqual(cli.clean_path('"C:\\My Docs\\cv.pdf"'), "C:\\My Docs\\cv.pdf")
        self.assertEqual(cli.clean_path("& 'C:\\My Docs\\cv.pdf'"), "C:\\My Docs\\cv.pdf")

    def test_cost_counts_returned_jobs(self):
        src = sources.BY_KEY["hirist"]
        run = {"chargedEventCounts": {"apify-default-dataset-item": 0}}
        self.assertAlmostEqual(core.charged(src, run, [{}] * 12), 0.036)

    def test_account_and_usage_from_api_shapes(self):
        class Client(apify.Apify):
            def _req(self, method, path, params=None, body=None, timeout=None):
                if path == "/users/me":
                    return {"data": {"username": "someone", "plan": {"id": "free"}}}
                if path == "/users/me/limits":
                    return {"data": {"monthlyUsageCycle": {"startAt": "2026-11-01T00:00:00.000Z", "endAt": "2026-12-01T00:00:00.000Z"},
                                     "limits": {"maxMonthlyUsageUsd": 5}, "current": {"monthlyUsageUsd": 1.25}}}
                if path == "/actor-runs":
                    return {"data": {"items": [{"actId": "A", "startedAt": "2026-11-05T10:00:00.000Z", "usageTotalUsd": 0.2},
                                               {"actId": "A", "startedAt": "2026-11-06T10:00:00.000Z", "usageTotalUsd": 0.1},
                                               {"actId": "B", "startedAt": "2026-10-20T10:00:00.000Z", "usageTotalUsd": 9}]}}
                raise AssertionError(path)

        acct = Client("t").account()
        self.assertEqual((acct["plan"], acct["left"]), ("FREE", 3.75))
        used = Client("t").usage_by_actor(acct["cycle_start"])
        self.assertEqual(used["A"]["runs"], 2)
        self.assertNotIn("B", used)


if __name__ == "__main__":
    unittest.main(verbosity=2)
