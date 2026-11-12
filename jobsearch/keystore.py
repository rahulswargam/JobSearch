"""Remembered settings live in your user environment variables, outside this project:

    APIFY_TOKEN        your Apify API key (pasted once)
    JOBSEARCH_RESUME   where your resume file is (its path only; the file itself is never copied)

Saving sets a variable permanently for your user account:
    Windows       a user environment variable (System Properties > Environment Variables > User variables),
                  the same as `setx NAME value`. Programs started afterwards see it.
    macOS/Linux   an `export NAME=...` line in your shell start-up file (~/.zshrc, ~/.bash_profile
                  or ~/.bashrc), so every new terminal has it.
It is also set for the current run straight away. Reading checks the running environment first, then
the saved value (so a terminal opened before it was saved still finds it).
Nothing here is ever written inside this repository, config.json, the output, or any log.
"""
import os
import re
import shlex
import sys
from pathlib import Path

NAME = "APIFY_TOKEN"
RESUME = "JOBSEARCH_RESUME"
ENV_NAMES = ("APIFY_TOKEN", "APIFY_API_TOKEN", "APIFY_API_KEY")
IS_WINDOWS = os.name == "nt"


# ---------------------------------------------------------------- Windows: user environment variables
def _win_get(name):
    import winreg
    places = ((winreg.HKEY_CURRENT_USER, "Environment"),
              (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"))
    for root, path in places:
        try:
            with winreg.OpenKey(root, path) as k:
                val = str(winreg.QueryValueEx(k, name)[0] or "").strip()
            if val:
                return val
        except OSError:
            continue
    return None


def _win_broadcast():
    """Tell Windows the environment changed, so newly started programs pick it up."""
    try:
        import ctypes
        result = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 3000, ctypes.byref(result))
    except Exception:
        pass


def _win_set(name, value):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
    _win_broadcast()


def _win_delete(name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, name)
    except OSError:
        return False
    _win_broadcast()
    return True


# ---------------------------------------------------------------- macOS / Linux: shell start-up file
def _home():
    return Path(os.environ.get("JOBSEARCH_PROFILE_HOME") or Path.home())


def profile_file():
    """The start-up file your terminal reads: ~/.zshrc for zsh (the macOS default), else bash's."""
    shell = os.path.basename(os.environ.get("SHELL", "") or ("zsh" if sys.platform == "darwin" else "bash"))
    if shell == "zsh":
        return _home() / ".zshrc"
    if shell == "bash":
        return _home() / (".bash_profile" if sys.platform == "darwin" else ".bashrc")
    return _home() / ".profile"


def _block_re(name):
    """This tool's block for one variable (and the older single-key block, for APIFY_TOKEN)."""
    new = rf"# >>> jobsearch: {re.escape(name)} >>>\n.*?# <<< jobsearch: {re.escape(name)} <<<\n?"
    old = r"# >>> jobsearch: Apify API key >>>\n.*?# <<< jobsearch <<<\n?"
    return re.compile(rf"\n?(?:{new}{'|' + old if name == NAME else ''})", re.S)


def _unix_get(name):
    candidates = [profile_file()] + [_home() / f for f in (".zshrc", ".zprofile", ".bash_profile", ".bashrc", ".profile")]
    for f in dict.fromkeys(candidates):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in re.finditer(rf"^\s*export\s+{re.escape(name)}=(.*)$", text, re.M):
            try:
                parts = shlex.split(m.group(1), comments=True)
            except ValueError:
                continue
            if parts and parts[0]:
                return parts[0]
    return None


def _unix_set(name, value):
    f = profile_file()
    old = f.read_text(encoding="utf-8") if f.is_file() else ""
    body = _block_re(name).sub("\n", old).rstrip("\n")
    block = f"# >>> jobsearch: {name} >>>\nexport {name}={shlex.quote(value)}\n# <<< jobsearch: {name} <<<\n"
    f.write_text((body + "\n\n" if body else "") + block, encoding="utf-8")


def _unix_delete(name):
    f = profile_file()
    if not f.is_file():
        return False
    old = f.read_text(encoding="utf-8")
    new = _block_re(name).sub("\n", old)
    if new == old:
        return False
    f.write_text(new.rstrip("\n") + "\n", encoding="utf-8")
    return True


# ---------------------------------------------------------------- the saved (persistent) value
def persist_get(name):
    return _win_get(name) if IS_WINDOWS else _unix_get(name)


def persist_set(name, value):
    return _win_set(name, value) if IS_WINDOWS else _unix_set(name, value)


def persist_delete(name):
    return _win_delete(name) if IS_WINDOWS else _unix_delete(name)


def where(name=NAME):
    """Where a variable is kept, in words, for messages."""
    if IS_WINDOWS:
        return f"the {name} environment variable (your Windows user variables)"
    return f"the {name} environment variable (in ~/{profile_file().name})"


where_saved = where


# ---------------------------------------------------------------- any remembered setting
def set_var(name, value):
    """Save a variable for good, and for this run. Returns where it was saved."""
    persist_set(name, value)
    os.environ[name] = value
    return where(name)


def get_var(name):
    """The variable from the running environment, else its saved value (also set for this run)."""
    val = os.environ.get(name, "").strip()
    if val:
        return val
    try:
        val = persist_get(name)
    except Exception:
        val = None
    if val:
        os.environ[name] = val
    return val or None


def forget_var(name):
    """Remove a saved variable. Returns True if there was one."""
    try:
        removed = persist_delete(name)
    except Exception:
        removed = False
    if os.environ.pop(name, None):
        removed = True
    return bool(removed)


# ---------------------------------------------------------------- the API key
def save(token):
    """Save the key as APIFY_TOKEN. Returns where it was saved."""
    return set_var(NAME, token)


def forget():
    return forget_var(NAME)


def find():
    """(key, where it came from): APIFY_TOKEN (or similar names), running environment first, then saved."""
    for name in ENV_NAMES:
        val = get_var(name)
        if val:
            return val, f"the {name} environment variable"
    moved = _move_from_credential_manager()
    if moved:
        return moved, f"the {NAME} environment variable (moved there from the system password store)"
    return None, None


def from_environment():
    return find()


def _move_from_credential_manager():
    """Earlier versions kept the key in Windows Credential Manager / macOS Keychain. Move it to APIFY_TOKEN once."""
    if os.environ.get("JOBSEARCH_NO_MIGRATE"):
        return None
    try:
        import keyring
        tok = keyring.get_password("jobsearch-apify", "api-key")
    except Exception:
        return None
    if not tok:
        return None
    try:
        save(tok)
        keyring.delete_password("jobsearch-apify", "api-key")
    except Exception:
        return tok  # still usable this run
    return tok


# ---------------------------------------------------------------- the resume
def saved_resume():
    """The resume path saved last time (JOBSEARCH_RESUME), or None."""
    return get_var(RESUME)


def save_resume(path):
    return set_var(RESUME, str(Path(path).expanduser().resolve()))


def forget_resume():
    return forget_var(RESUME)
