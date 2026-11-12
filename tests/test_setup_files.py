"""The setup files must install every package the code imports, match requirements.txt, and stay valid scripts."""
import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIN = ROOT / "setup-windows.ps1"
MAC = ROOT / "setup-mac.command"
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


class SetupFiles(unittest.TestCase):
    def packages(self, text, var):
        m = re.search(rf"^\s*\${var}\s*=\s*@\(([^)]*)\)", text, re.M)          # PowerShell: $Required = @('a', 'b')
        if m:
            return set(re.findall(r"'([^']+)'", m.group(1)))
        m = re.search(rf'^{var.upper()}="([^"]*)"', text, re.M)                  # bash: REQUIRED="a b"
        return set(m.group(1).split())

    def test_every_imported_package_is_installed_by_both(self):
        needed = {IMPORT_NAMES.get(m, m) for m in third_party_imports()}
        self.assertTrue(needed, "found no third-party imports")
        for f in (WIN, MAC):
            text = f.read_text(encoding="utf-8")
            installed = self.packages(text, "Required") | self.packages(text, "Optional")
            self.assertLessEqual(needed, installed, f"{f.name} misses {needed - installed}")

    def test_both_files_and_requirements_agree(self):
        win, mac = WIN.read_text(encoding="utf-8"), MAC.read_text(encoding="utf-8")
        self.assertEqual(self.packages(win, "Required"), self.packages(mac, "Required"))
        self.assertEqual(self.packages(win, "Optional"), self.packages(mac, "Optional"))
        req_text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        req = {l.split("#")[0].strip() for l in req_text.splitlines() if l.split("#")[0].strip()}
        self.assertEqual(req | {"pip"}, self.packages(win, "Required"))
        optional_comment = set(re.findall(r"^#\s+(\w+)\s{2,}", req_text, re.M))
        self.assertEqual(optional_comment, self.packages(win, "Optional"))

    def test_tools_cover_python_tk_git_font_browser(self):
        win, mac = WIN.read_text(encoding="utf-8"), MAC.read_text(encoding="utf-8")
        for needle in ("Python.Python.3", "Include_tcltk=1", "Git.Git", "Microsoft.WindowsTerminal", "googlesans-code",
                       "import tkinter", "Default-Browser"):
            self.assertIn(needle, win)
        for needle in ("python@3", "python-tk@3", "brew_ensure git", "font-google-sans-code", "import tkinter", "Homebrew/install"):
            self.assertIn(needle, mac)

    def test_windows_file_is_a_plain_powershell_script(self):
        raw = WIN.read_bytes()
        self.assertTrue(raw.startswith(b"<#" + CRLF), "starts with its help comment, CRLF line endings")
        self.assertNotIn(LF, raw.replace(CRLF, b""), "every line must end in CRLF")
        text = raw.decode("ascii")  # Windows PowerShell 5.1 reads BOM-less scripts as ANSI: keep it ASCII
        self.assertIn("param(", text)
        # Antivirus treats "run this file's text as code" as malware behaviour (Defender blocked it): never do that
        for pattern in ("Invoke-Expression", "iex ", "ReadAllText($env:", "[scriptblock]::Create", "-EncodedCommand"):
            self.assertNotIn(pattern, text)
        # File names can contain [ ] (the font is "GoogleSansCode[MONO,wght].ttf"); without -LiteralPath PowerShell
        # treats them as wildcards and silently does nothing. Only the registry lookup ($key) may skip it.
        loose = [l.strip() for l in text.splitlines()
                 if re.search(r"\b(Test-Path|Copy-Item|Get-Content|Set-Content|Remove-Item)\s+\$(?!key\b)", l)]
        self.assertEqual(loose, [], "use -LiteralPath for file paths")

    def test_mac_files_are_unix_scripts(self):
        for f in (MAC, ROOT / "run.command"):
            raw = f.read_bytes()
            self.assertTrue(raw.startswith(b"#!/bin/bash" + LF))
            self.assertNotIn(CR, raw, f"{f.name} must use LF line endings to run on macOS")
        attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.command text eol=lf", attrs)
        self.assertIn("*.bat text eol=crlf", attrs)
        self.assertIn("*.ps1 text eol=crlf", attrs)

    def test_launchers_prefer_the_setup_venv(self):
        self.assertIn(r".venv\Scripts\python.exe", (ROOT / "run.bat").read_text(encoding="utf-8"))
        self.assertIn(".venv/bin/python", (ROOT / "run.command").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
