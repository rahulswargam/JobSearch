"""Offline tests for the guided run: key found / registered once / changed, resume file window, ticking sources
with the live debit line, save folder, budget and credit checks. Menus are scripted and Apify is faked; the key
store is a temporary file (never your real Credential Manager or Keychain), and nothing is written to Downloads."""
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

from jobsearch import apify, cli, core, keystore, sources, ui  # noqa: E402
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
        self.steps, self.asked, self.footer, self.defaults = list(steps), [], "", {}

    def take(self, kind, question):
        self.asked.append((kind, question))
        if not self.steps:
            raise AssertionError(f"unexpected {kind}: {question!r}")
        k, expect, answer = self.steps.pop(0)
        if k != kind or expect not in question:
            raise AssertionError(f"expected {k} {expect!r}, got {kind} {question!r}")
        return answer

    def select(self, question, options, default=0, answer_label=None):
        self.options = options
        return self.take("select", question)

    def checkbox(self, question, columns, rows, selected, footer, min_selected=1, answer=None):
        keys = self.take("checkbox", question)
        self.preselected = set(selected)
        self.footer = "".join(t for _, t in footer(keys))
        return keys

    def secret(self, message):
        return self.take("secret", message)

    def pick_file(self, title="", initialdir=None):
        return self.take("file", title)

    def pick_folder(self, title="", initialdir=None):
        return self.take("folder", title)

    def ask_text(self, message, default=""):
        self.defaults[message] = default
        answer = self.take("text", message)
        return answer if answer is not None else default


class Guided(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.cwd = os.getcwd()
        os.chdir(self.dir)
        (self.dir / "config.json").write_text(json.dumps({"roles": ["Site Reliability Engineer"], "location": "India",
                                                          "preferred_locations": ["Pune"], "sources": ["linkedin", "naukri"]}), encoding="utf-8")
        self.downloads = self.dir / "Downloads" / "JobSearch"
        FakeApify.runs = []
        self.opened, self.folders = [], []
        env = {k: v for k, v in os.environ.items() if k not in keystore.ENV_NAMES}
        env.update(JOBSEARCH_KEYSTORE="file", JOBSEARCH_HOME=str(self.dir / "home"))
        width = ui.console.width
        ui.console.width = 160
        self.addCleanup(setattr, ui.console, "width", width)
        env_only = lambda: next(((os.environ[n], f"the {n} environment variable") for n in keystore.ENV_NAMES if os.environ.get(n)), (None, None))
        for p in (mock.patch.dict(os.environ, env, clear=True), mock.patch.object(cli, "Apify", FakeApify),
                  mock.patch.object(core, "Apify", FakeApify), mock.patch.object(ui, "interactive", lambda: True),
                  mock.patch.object(keystore, "from_environment", env_only),
                  mock.patch.object(cli, "default_output_dir", lambda: self.downloads),
                  mock.patch.object(ui, "open_path", lambda p: self.folders.append(str(p))),
                  mock.patch.object(webbrowser, "open", lambda url, *x, **k: self.opened.append(url))):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def run_cli(self, argv, steps):
        script = Script(steps)
        buf = io.StringIO()
        names = ("select", "checkbox", "secret", "pick_file", "pick_folder", "ask_text")
        patches = [mock.patch.object(ui, n, getattr(script, n)) for n in names]
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

    def project_files_text(self):
        home = self.dir / "home"
        return "".join(f.read_text(encoding="utf-8", errors="ignore") for f in self.dir.rglob("*")
                       if f.is_file() and home not in f.parents)

    def test_first_run_registers_key_then_second_run_does_not_ask(self):
        code, out, s = self.run_cli([], [
            ("select", "How do you want to add your API key?", 0),   # open the key page
            ("secret", "Paste your Apify API key", KEY),
            ("file", "Choose your resume", str(RESUME)),
            ("select", "Search settings", 0),
            ("checkbox", "Which job sources", ["linkedin", "naukri", "india-feed"]),
            ("select", "Where should the job links page be saved?", 0),
            ("select", "Ready?", 0),
            ("select", "What next?", 0),
        ])
        self.assertEqual(code, 0, out)
        for expected in ("Built by", "Rahul Swargam", "Visit my website", "STEP 1 OF 4", "STEP 4 OF 4", "No API key found",
                         "Key registered", "won't be asked for it again", "Signed in to Apify as tester", "REVIEW", "RESULTS"):
            self.assertIn(expected, out)
        for gone in ("Ctrl+click", ui.APIFY_KEY_PAGE, "rahulswargam.online", "looked for APIFY_TOKEN"):
            self.assertNotIn(gone, out)                                 # links are clickable labels, not printed URLs
        self.assertEqual(self.opened[0], ui.APIFY_KEY_PAGE)
        self.assertTrue(self.opened[-1].endswith("job_links.html"))
        self.assertIn("up to $0.186 will be debited", s.footer)
        self.assertTrue((self.downloads / "job_links.html").is_file())  # saved to Downloads/JobSearch by default
        cfg = json.loads((self.dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(Path(cfg["output_dir"]), self.downloads)        # remembered for next time
        self.assertNotIn("resume", cfg)
        self.assertEqual(keystore.load(), KEY)                          # registered once...
        self.assertNotIn(KEY, self.project_files_text())                # ...outside the project and the output
        self.assertNotIn(KEY, out)

        # Second run: the key is found and not asked for; only the option to change it
        FakeApify.runs = []
        code, out, s = self.run_cli(["--sources", "naukri"], [
            ("select", "Which API key should this search use?", 0),
            ("file", "Choose your resume", str(RESUME)),
            ("select", "Search settings", 0),
            ("select", "Where should the job links page be saved?", 0),
            ("select", "Ready?", 0),
            ("select", "What next?", 2),
        ])
        self.assertEqual(code, 0, out)
        self.assertIn("API key found", out)
        self.assertNotIn("Paste your Apify API key", "".join(q for _, q in s.asked))
        self.assertEqual([o[0] for o in s.options], ["Open the job links page in my browser", "Open the folder", "Done"])

    def test_change_api_key_replaces_the_registered_one(self):
        keystore.save(KEY)
        code, out, _ = self.run_cli(["--resume", str(RESUME), "--sources", "naukri", "--out", str(self.dir / "out")], [
            ("select", "Which API key should this search use?", 1),     # Change API key
            ("select", "How do you want to add your API key?", 1),
            ("secret", "Paste your Apify API key", KEY2),
            ("select", "Search settings", 0),
            ("select", "Ready?", 0),
            ("select", "What next?", 2),
        ])
        self.assertEqual(code, 0, out)
        self.assertIn("Signed in to Apify as second", out)
        self.assertEqual({r["token"] for r in FakeApify.runs}, {KEY2})
        self.assertEqual(keystore.load(), KEY2)

    def test_env_variable_is_found_without_asking(self):
        with mock.patch.dict(os.environ, {"APIFY_TOKEN": KEY}):
            code, out, _ = self.run_cli(["--resume", str(RESUME), "--sources", "naukri", "--out", str(self.dir / "out")], [
                ("select", "Which API key should this search use?", 0),
                ("select", "Search settings", 0),
                ("select", "Ready?", 0),
                ("select", "What next?", 1),
            ])
        self.assertEqual(code, 0, out)
        self.assertIn("API key found", out)
        self.assertIn("APIFY_TOKEN", out)
        self.assertEqual(self.folders, [str(self.dir / "out")])         # "Open the folder"

    def test_choose_another_folder_fills_in_the_path(self):
        keystore.save(KEY)
        picked = self.dir / "My Jobs"
        code, out, s = self.run_cli(["--resume", str(RESUME), "--sources", "naukri"], [
            ("select", "Which API key", 0),
            ("select", "Search settings", 0),
            ("select", "Where should the job links page be saved?", 1),
            ("folder", "Choose where to save", str(picked)),
            ("text", "Save to", None),                                   # Enter accepts the filled-in path
            ("select", "Ready?", 0),
            ("select", "What next?", 2),
        ])
        self.assertEqual(code, 0, out)
        self.assertEqual(s.defaults["Save to (Enter to confirm, or edit the path):"], str(picked))
        self.assertTrue((picked / "job_links.html").is_file())
        self.assertEqual(Path(json.loads((self.dir / "config.json").read_text(encoding="utf-8"))["output_dir"]), picked)

    def test_short_on_credit_changes_key_mid_way(self):
        keystore.save(LOW)
        code, out, _ = self.run_cli(["--resume", str(RESUME), "--sources", "linkedin,naukri", "--out", str(self.dir / "out")], [
            ("select", "Which API key", 0),
            ("select", "Search settings", 0),
            ("select", "more than the $0.05 credit left", 0),           # Change API key
            ("select", "How do you want to add your API key?", 1),
            ("secret", "Paste your Apify API key", KEY),
            ("select", "Ready?", 0),
            ("select", "What next?", 2),
        ])
        self.assertEqual(code, 0, out)
        self.assertEqual({r["token"] for r in FakeApify.runs}, {KEY})
        self.assertEqual(keystore.load(), KEY)

    def test_over_cap_can_raise_it(self):
        keystore.save(KEY)
        picks = ["linkedin", "remote", "wellfound", "hirist", "upwork-neatrat"]
        code, out, _ = self.run_cli(["--resume", str(RESUME), "--out", str(self.dir / "out")], [
            ("select", "Which API key", 0),
            ("select", "Search settings", 0),
            ("checkbox", "Which job sources", picks),
            ("select", "over your $0.50 per-search cap", 0),
            ("select", "Ready?", 0),
            ("select", "What next?", 2),
        ])
        self.assertEqual(code, 0, out)
        total = sum(sources.BY_KEY[k].estimate(sources.Search(roles=["x"])) for k in picks)
        self.assertGreater(total, 0.5)
        self.assertGreaterEqual(sum(r["cap"] for r in FakeApify.runs), total)

    def test_resume_window_cancelled_then_typed(self):
        keystore.save(KEY)
        code, out, _ = self.run_cli(["--sources", "naukri", "--out", str(self.dir / "out")], [
            ("select", "Which API key", 0),
            ("file", "Choose your resume", ""),
            ("select", "No file was chosen", 1),
            ("text", "Paste the full path", f'"{RESUME}"'),
            ("select", "Search settings", 0),
            ("select", "Ready?", 1),                                     # cancel
        ])
        self.assertEqual(code, 1)
        self.assertIn("Cancelled; nothing was spent", out)
        self.assertEqual(FakeApify.runs, [])

    def test_stale_registered_key_is_removed_and_asked_again(self):
        keystore.save("revoked-key")
        code, out, _ = self.run_cli(["--resume", str(RESUME), "--sources", "naukri", "--out", str(self.dir / "out")], [
            ("select", "How do you want to add your API key?", 1),
            ("secret", "Paste", KEY),
            ("select", "Search settings", 0),
            ("select", "Ready?", 1),
        ])
        self.assertIn("no longer works", out)
        self.assertEqual(keystore.load(), KEY)

    def test_rejected_keys(self):
        code, out, _ = self.run_cli(["--resume", str(RESUME), "--sources", "naukri"], [
            ("select", "How do you want to add your API key?", 1),
            ("secret", "Paste", "wrong-1"), ("secret", "Paste", "wrong-2"), ("secret", "Paste", "wrong-3"),
        ])
        self.assertEqual(code, 1)
        self.assertIn("Three keys were rejected", out)
        self.assertIsNone(keystore.load())

    def test_scheduled_run_uses_registered_key(self):
        keystore.save(KEY)
        with mock.patch.object(ui, "interactive", lambda: False):
            code, out, _ = self.run_cli(["--resume", str(RESUME), "-y", "--sources", "naukri", "--out", str(self.dir / "out")], [])
        self.assertEqual(code, 0, out)
        self.assertEqual({r["token"] for r in FakeApify.runs}, {KEY})

    def test_scheduled_run_without_key_explains(self):
        with mock.patch.object(ui, "interactive", lambda: False):
            code, out, _ = self.run_cli(["--resume", str(RESUME), "-y"], [])
        self.assertEqual(code, 1)
        self.assertIn("No API key found", out)

    def test_forget_key(self):
        keystore.save(KEY)
        code, out, _ = self.run_cli(["forget-key"], [])
        self.assertIn("removed", out)
        self.assertIsNone(keystore.load())

    def test_credits_command(self):
        keystore.save(KEY)
        with mock.patch.object(ui, "interactive", lambda: False):
            code, out, _ = self.run_cli(["credits"], [])
        self.assertEqual(code, 0, out)
        self.assertIn("3 runs · $0.31", out)
        self.assertRegex(out, r"linkedin\s+crawlworks/linkedin-jobs-scraper\s+\$0\.125\s+31")


class Pieces(unittest.TestCase):
    def test_keystore_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"JOBSEARCH_KEYSTORE": "file", "JOBSEARCH_HOME": d}):
            self.assertIsNone(keystore.load())
            keystore.save(KEY)
            self.assertEqual(keystore.load(), KEY)
            if os.name == "nt":
                self.assertNotIn(KEY, (Path(d) / "apify-key.json").read_text(encoding="utf-8"))  # encrypted on Windows
            self.assertTrue(keystore.forget())
            self.assertIsNone(keystore.load())

    def test_parse_picks(self):
        cur = ["linkedin", "naukri"]
        self.assertEqual(sources.parse_picks("", cur), cur)
        self.assertEqual(sources.parse_picks("1, 2 5", cur), ["linkedin", "naukri", "india-feed"])
        self.assertNotIn("career-sites", sources.parse_picks("all", cur))
        for bad in ("0", "99", "monster", "3-1"):
            with self.assertRaises(ValueError):
                sources.parse_picks(bad, cur)

    def test_every_source_has_an_actor_id(self):
        self.assertTrue(all(s.actor_id for s in sources.ALL))

    def test_clean_path(self):
        self.assertEqual(cli.clean_path('"C:\\My Docs\\cv.pdf"'), "C:\\My Docs\\cv.pdf")
        self.assertEqual(cli.clean_path("& 'C:\\My Docs\\cv.pdf'"), "C:\\My Docs\\cv.pdf")
        self.assertEqual(cli.clean_path("'/Users/me/My Docs/cv.pdf'"), "/Users/me/My Docs/cv.pdf")  # macOS drag and drop

    def test_mac_pickers_build_valid_applescript(self):
        calls = []
        with mock.patch.object(ui, "IS_MAC", True), mock.patch.object(ui, "_osascript", lambda s: calls.append(s) or "/Users/me/cv.pdf"):
            self.assertEqual(ui.pick_file("Choose your resume"), "/Users/me/cv.pdf")
            ui.pick_folder("Choose where to save")
        self.assertIn('choose file with prompt "Choose your resume" of type {"pdf", "docx", "txt", "md"}', calls[0])
        self.assertIn('choose folder with prompt "Choose where to save"', calls[1])

    def test_downloads_dir(self):
        self.assertTrue(str(ui.downloads_dir()).lower().endswith("downloads"))

    def test_cost_counts_returned_jobs(self):
        run = {"chargedEventCounts": {"apify-default-dataset-item": 0}}
        self.assertAlmostEqual(core.charged(sources.BY_KEY["hirist"], run, [{}] * 12), 0.036)

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
