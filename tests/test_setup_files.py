"""The one-click setup files must install every package the code imports, agree with requirements.txt, stay
valid scripts for their OS, and avoid anything antivirus treats as malware behaviour. Also tests setup_helper."""
import ast
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jobsearch import setup_helper  # noqa: E402

WIN = ROOT / "setup-windows.bat"
MAC = ROOT / "setup-mac.sh"
IMPORT_NAMES = {"fitz": "PyMuPDF", "pymupdf": "PyMuPDF", "prompt_toolkit": "prompt_toolkit", "pypdf": "pypdf", "rich": "rich",
                "keyring": "keyring", "certifi": "certifi"}
CRLF, LF, CR = b"\r\n", b"\n", b"\r"


def third_party_imports():
    std = set(sys.stdlib_module_names)
    found = set()
    for f in (ROOT / "jobsearch").glob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else \
                [n.module] if isinstance(n, ast.ImportFrom) and n.module and n.level == 0 else []
            found |= {m.split(".")[0] for m in names if m.split(".")[0] not in std}
    return found - {"jobsearch"}


def packages(text, var):
    m = re.search(rf'^set "{var.upper()}=([^"]*)"', text, re.M | re.I)   # batch: set "REQUIRED=a b"
    if not m:
        m = re.search(rf'^{var.upper()}="([^"]*)"', text, re.M)          # bash: REQUIRED="a b"
    return set(m.group(1).split())


class SetupFiles(unittest.TestCase):
    def test_every_imported_package_is_installed_by_both(self):
        needed = {IMPORT_NAMES.get(m, m) for m in third_party_imports()}
        self.assertTrue(needed, "found no third-party imports")
        for f in (WIN, MAC):
            text = f.read_text(encoding="utf-8")
            installed = packages(text, "Required") | packages(text, "Optional")
            self.assertLessEqual(needed, installed, f"{f.name} misses {needed - installed}")

    def test_both_files_and_requirements_agree(self):
        win, mac = WIN.read_text(encoding="utf-8"), MAC.read_text(encoding="utf-8")
        self.assertEqual(packages(win, "Required"), packages(mac, "Required"))
        self.assertEqual(packages(win, "Optional"), packages(mac, "Optional"))
        req_text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        req = {l.split("#")[0].strip() for l in req_text.splitlines() if l.split("#")[0].strip()}
        self.assertEqual(req | {"pip"}, packages(win, "Required"))
        self.assertEqual(set(re.findall(r"^#\s+(\w+)\s{2,}", req_text, re.M)), packages(win, "Optional"))

    def test_tools_cover_python_tk_git_terminal_font_browser(self):
        win, mac = WIN.read_text(encoding="utf-8"), MAC.read_text(encoding="utf-8")
        for needle in ("Python.Python.3", "Include_tcltk=1", "Git.Git", "Microsoft.WindowsTerminal", "setup_helper font",
                       "setup_helper terminal-font", "import tkinter", "setup_helper browser", "setup_helper selftest", "-m venv"):
            self.assertIn(needle, win)
        for needle in ("python@3", "python-tk@3", "brew_ensure git", "font-google-sans-code", "import tkinter",
                       "Homebrew/install", "-m venv"):
            self.assertIn(needle, mac)

    def test_windows_file_is_plain_batch(self):
        raw = WIN.read_bytes()
        self.assertTrue(raw.startswith(b"@echo off" + CRLF))
        self.assertNotIn(LF, raw.replace(CRLF, b""), "every line must end in CRLF for cmd.exe")
        text = raw.decode("ascii")  # plain ASCII so every Windows code page reads it the same way
        # Defender blocked an earlier version that ran its own text as PowerShell code: no PowerShell commands at all
        commands = "\n".join(l for l in text.splitlines() if not l.lstrip().lower().startswith("rem")).lower()
        for pattern in ("powershell", "pwsh", "invoke-expression", "iex ", "-encodedcommand", "frombase64"):
            self.assertNotIn(pattern, commands)
        labels = set(re.findall(r"^:(\w+)", text, re.M))
        for called in set(re.findall(r"call :(\w+)", text)):
            self.assertIn(called, labels, f"call :{called} has no label")

    def test_mac_files_are_unix_scripts(self):
        for f in (MAC, ROOT / "run.command"):
            raw = f.read_bytes()
            self.assertTrue(raw.startswith(b"#!/bin/bash" + LF))
            self.assertNotIn(CR, raw, f"{f.name} must use LF line endings to run on macOS")
        attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        for rule in ("*.sh text eol=lf", "*.command text eol=lf", "*.bat text eol=crlf"):
            self.assertIn(rule, attrs)

    def test_launchers_prefer_the_setup_venv(self):
        self.assertIn(r".venv\Scripts\python.exe", (ROOT / "run.bat").read_text(encoding="utf-8"))
        self.assertIn(".venv/bin/python", (ROOT / "run.command").read_text(encoding="utf-8"))


class Helper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.summary = self.dir / "summary.txt"
        self.summary.write_text("", encoding="utf-8")
        p = mock.patch.dict(os.environ, {"JS_SUMMARY": str(self.summary), "JS_CHECK": "0"})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def rows(self):
        return [l.split("|") for l in self.summary.read_text(encoding="utf-8").splitlines()]

    def quiet(self, fn, *a, **k):
        with redirect_stdout(io.StringIO()) as out:
            code = fn(*a, **k)
        return code, out.getvalue()

    def test_terminal_font_sets_the_monospace_name_and_keeps_a_backup(self):
        settings = self.dir / "settings.json"
        settings.write_text(json.dumps({"profiles": {"defaults": {}, "list": [{"name": "PowerShell"}]}, "theme": "dark"}), encoding="utf-8")
        code, out = self.quiet(setup_helper.terminal_font, [settings])
        data = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(data["profiles"]["defaults"]["font"]["face"], "Google Sans Code Monospace")
        self.assertEqual(data["theme"], "dark")                                    # everything else kept
        self.assertTrue((self.dir / "settings.json.before-jobsearch.bak").is_file())
        code, out = self.quiet(setup_helper.terminal_font, [settings])
        self.assertIn("already uses", out)

    def test_terminal_font_leaves_files_with_comments_alone(self):
        settings = self.dir / "settings.json"
        settings.write_text('{ // my comment\n "profiles": {} }', encoding="utf-8")
        code, out = self.quiet(setup_helper.terminal_font, [settings])
        self.assertIn("Set it by hand", out)
        self.assertIn("// my comment", settings.read_text(encoding="utf-8"))

    def test_packages_compare_with_pypi(self):
        newest = {"pip": None, "rich": "999.0", "PyMuPDF": "2.1", "not-a-real-package-x": "1.0"}.get
        code, out = self.quiet(setup_helper.packages, ["pip", "rich"], ["not-a-real-package-x"], latest=newest)
        self.assertEqual(code, 0)
        rows = {r[0]: r for r in self.rows()}
        self.assertEqual(rows["pip"][2], "latest")
        self.assertIn("newest for Python", rows["rich"][2])                         # PyPI has newer than installed
        self.assertEqual(rows["not-a-real-package-x"][2], "optional, skipped")
        code, _ = self.quiet(setup_helper.packages, ["not-a-real-package-x"], [], latest=newest)
        self.assertEqual(code, 1)                                                   # a missing required package fails

    def test_font_check_mode_and_already_installed(self):
        fonts = self.dir / "Fonts"
        fonts.mkdir()
        release = {"tag_name": "v7.001", "assets": [{"name": "GoogleSansCode-v7.001.zip", "browser_download_url": "https://x"}]}
        with mock.patch.object(setup_helper, "fetch_json", lambda url, timeout=30: release), \
                mock.patch.object(setup_helper, "font_dir", lambda: fonts), \
                mock.patch.object(setup_helper, "load_fonts", lambda files: None):
            with mock.patch.dict(os.environ, {"JS_CHECK": "1"}):
                self.quiet(setup_helper.font)
            (fonts / "GoogleSansCode[MONO,wght].ttf").write_bytes(b"x")         # brackets in the name, as released
            (fonts / "GoogleSansCode.version.txt").write_text("v7.001", encoding="ascii")
            code, out = self.quiet(setup_helper.font)
        self.assertEqual([r[2] for r in self.rows()], ["would install", "latest"])
        self.assertIn("already the latest", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
