"""Helpers for setup-windows.bat and setup-mac.sh.

Standard library only: it runs with the freshly installed Python, before the project's .venv exists.
Each command prints coloured status lines and adds a row to the setup summary file ($JS_SUMMARY).

    python -m jobsearch.setup_helper font               install / update Google Sans Code (Windows)
    python -m jobsearch.setup_helper terminal-font      use it in Windows Terminal (keeps a backup)
    python -m jobsearch.setup_helper packages A B --optional C D
                                                        report installed versions vs the newest on PyPI
    python -m jobsearch.setup_helper selftest           run the offline checks and start the tool once
    python -m jobsearch.setup_helper browser            which browser opens the job links page
Set JS_CHECK=1 to only report (change nothing).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FONT_RELEASE = "https://api.github.com/repos/googlefonts/googlesans-code/releases/latest"
TERMINAL_FACE = "Google Sans Code Monospace"  # the name Windows Terminal (DirectWrite) knows the monospaced font by
FONT_REG = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"

if os.name == "nt":
    os.system("")  # switch the Windows console into colour mode
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

GREEN, YELLOW, RED, CYAN, RESET = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[0m"


def checking():
    return os.environ.get("JS_CHECK") == "1"


def line(tag, colour, text):
    print(f"  {colour}[{tag}]{RESET} {text}", flush=True)


def ok(text):
    line(" OK ", GREEN, text)


def info(text):
    line(" .. ", CYAN, text)


def warn(text):
    line(" !! ", YELLOW, text)


def bad(text):
    line("FAIL", RED, text)


def record(tool, version, status):
    path = os.environ.get("JS_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{tool}|{version or '-'}|{status}\n")


def fetch_json(url, timeout=30):
    with urlopen(Request(url, headers={"User-Agent": "jobsearch-setup"}), timeout=timeout) as r:
        return json.load(r)


# ---------------------------------------------------------------------------------------------- font (Windows)
def font_dir():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Microsoft" / "Windows" / "Fonts"


def load_fonts(files):
    """Make fonts usable now: registry entries alone only apply at the next sign-in."""
    try:
        import ctypes
        for f in files:
            ctypes.windll.gdi32.AddFontResourceW(str(f))
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001D, 0, 0, 2, 3000, None)
    except Exception:
        pass


def font():
    try:
        rel = fetch_json(FONT_RELEASE)
    except Exception as e:
        warn(f"Couldn't reach GitHub for the font ({e}); skipped.")
        record("Google Sans Code font", "-", "skipped")
        return 0
    tag = rel.get("tag_name", "")
    asset = next((a for a in rel.get("assets", []) if re.fullmatch(r"GoogleSansCode-v[\d.]+\.zip", a.get("name", ""))), None)
    if not asset:
        warn(f"No font download in release {tag}; skipped.")
        record("Google Sans Code font", "-", "skipped")
        return 0
    fdir = font_dir()
    marker = fdir / "GoogleSansCode.version.txt"
    have = sorted(fdir.glob("GoogleSansCode*.ttf"))
    have_tag = marker.read_text(encoding="ascii").strip() if marker.is_file() else ""
    if checking():
        if have and have_tag == tag:
            ok(f"Google Sans Code {tag} (latest)")
            record("Google Sans Code font", tag, "latest")
        else:
            info(f"Google Sans Code would install {tag}")
            record("Google Sans Code font", tag, "would install")
        return 0
    if have and have_tag == tag:
        load_fonts(have)
        ok(f"Google Sans Code {tag} is already the latest")
        record("Google Sans Code font", tag, "latest")
        return 0
    info(f"Installing Google Sans Code {tag} for your account ...")
    tmp = Path(tempfile.mkdtemp(prefix="jobsearch-font-"))
    try:
        zpath = tmp / asset["name"]
        with urlopen(Request(asset["browser_download_url"], headers={"User-Agent": "jobsearch-setup"}), timeout=120) as r, open(zpath, "wb") as f:
            shutil.copyfileobj(r, f)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(tmp / "x")
        ttf = [p for p in (tmp / "x").rglob("*.ttf") if "[" in p.name] or list((tmp / "x").rglob("*.ttf"))
        fdir.mkdir(parents=True, exist_ok=True)
        import winreg
        copied = []
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, FONT_REG) as key:
            for p in ttf:
                dest = fdir / p.name
                try:
                    shutil.copyfile(p, dest)
                except OSError:
                    warn(f"{p.name} is in use; close Windows Terminal and run setup again to update it.")
                if not dest.is_file():
                    continue
                face = "Google Sans Code Italic (TrueType)" if "Italic" in p.name else "Google Sans Code (TrueType)"
                winreg.SetValueEx(key, face, 0, winreg.REG_SZ, str(dest))
                copied.append(dest)
        if not copied:
            warn("The font files couldn't be copied; skipped.")
            record("Google Sans Code font", "-", "install failed")
            return 0
        marker.write_text(tag, encoding="ascii")
        load_fonts(copied)
        ok(f"Google Sans Code {tag} installed ({len(copied)} font files in {fdir})")
        record("Google Sans Code font", tag, "reinstalled" if have else "installed")
        return 0
    except Exception as e:
        warn(f"The font couldn't be installed: {e}")
        record("Google Sans Code font", "-", "skipped")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def terminal_settings_files():
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    candidates = [local / "Packages" / "Microsoft.WindowsTerminal_8wekyb3d8bbwe" / "LocalState" / "settings.json",
                  local / "Packages" / "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe" / "LocalState" / "settings.json",
                  local / "Microsoft" / "Windows Terminal" / "settings.json"]
    return [p for p in candidates if p.is_file()]


def terminal_font(files=None):
    files = terminal_settings_files() if files is None else files
    if not files:
        info(f"Open Windows Terminal once, then run setup again to set its font (or: Settings > Defaults > Appearance > Font face > {TERMINAL_FACE}).")
        return 0
    for p in files:
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            warn(f"Couldn't read {p} (it has comments). Set it by hand: Settings > Defaults > Appearance > Font face > {TERMINAL_FACE}.")
            continue
        profiles = data.setdefault("profiles", {})
        if not isinstance(profiles, dict):
            warn("Unusual Windows Terminal settings; set the font by hand.")
            continue
        fontcfg = profiles.setdefault("defaults", {}).setdefault("font", {})
        if fontcfg.get("face") == TERMINAL_FACE:
            ok(f"Windows Terminal already uses {TERMINAL_FACE}")
            continue
        backup = p.with_name(p.name + ".before-jobsearch.bak")
        if not backup.exists():
            shutil.copyfile(p, backup)
        fontcfg["face"] = TERMINAL_FACE
        p.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
        ok(f"Windows Terminal font set to {TERMINAL_FACE} (backup: {backup.name})")
    return 0


# ---------------------------------------------------------------------------------------------- packages
def pypi_latest(name):
    try:
        return fetch_json(f"https://pypi.org/pypi/{name}/json", timeout=20)["info"]["version"]
    except Exception:
        return None


def packages(required, optional, latest=pypi_latest):
    """Report each package's installed version against the newest on PyPI. Returns 1 if a required one is missing."""
    from importlib import metadata
    py = f"{sys.version_info[0]}.{sys.version_info[1]}"
    failed = 0
    for name in required + optional:
        try:
            ver = metadata.version(name)
        except metadata.PackageNotFoundError:
            ver = None
        newest = latest(name)
        if checking():
            if not ver:
                info(f"{name} would install")
                record(name, "-", "would install")
            elif newest and newest != ver:
                info(f"{name} {ver} may update (PyPI has {newest}; setup installs the newest that works with Python {py})")
                record(name, ver, f"may update (PyPI has {newest})")
            else:
                ok(f"{name} {ver} (latest)")
                record(name, ver, "latest")
            continue
        if ver:
            status = "latest" if not newest or newest == ver else f"newest for Python {py} (PyPI has {newest})"
            ok(f"{name} {ver}" + ("" if status == "latest" else f" - {status}"))
            record(name, ver, status)
        elif name in optional:
            warn(f"{name} (optional) isn't available for Python {py} yet; Job Search works without it.")
            record(name, "-", "optional, skipped")
        else:
            bad(f"{name} is missing")
            record(name, "-", "failed")
            failed = 1
    return failed


# ---------------------------------------------------------------------------------------------- checks
def selftest():
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout + r.stderr
    m = re.search(r"Ran (\d+) tests?", out)
    code = 0
    if r.returncode == 0 and re.search(r"^OK", out, re.M):
        ok(f"All {m.group(1) if m else '?'} offline checks passed")
    else:
        bad("Some checks failed:")
        print("\n".join(out.strip().splitlines()[-20:]))
        code = 1
    r = subprocess.run([sys.executable, "-m", "jobsearch", "sources"], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode == 0:
        ok("python -m jobsearch starts")
    else:
        bad("python -m jobsearch did not start")
        code = 1
    return code


def browser():
    name = "your default browser (Safari is built in)" if sys.platform == "darwin" else "Microsoft Edge"
    if os.name == "nt":
        try:
            import winreg
            path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
                prog = winreg.QueryValueEx(k, "ProgId")[0]
            names = [("MSEdge", "Microsoft Edge"), ("Chrome", "Google Chrome"), ("Firefox", "Mozilla Firefox"),
                     ("Brave", "Brave"), ("Opera", "Opera")]
            name = next((n for key, n in names if prog.startswith(key)), prog)
        except OSError:
            pass
    ok(f"Job links pages open in {name}")
    record("Web browser (for the HTML page)", name.replace("your default browser ", "default "), "present")
    return 0


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__)
        return 2
    cmd, rest = args[0], args[1:]
    if cmd == "font":
        return font()
    if cmd == "terminal-font":
        return terminal_font()
    if cmd == "packages":
        if "--optional" in rest:
            i = rest.index("--optional")
            return packages(rest[:i], rest[i + 1:])
        return packages(rest, [])
    if cmd == "selftest":
        return selftest()
    if cmd == "browser":
        return browser()
    print(f"Unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
