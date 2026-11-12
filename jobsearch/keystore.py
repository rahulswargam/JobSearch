"""Your Apify API key lives in the APIFY_TOKEN environment variable: pasted once, read back every run.

Saving sets it permanently for your user account, outside this project:
    Windows       a user environment variable (System Properties > Environment Variables > User variables),
                  the same as `setx APIFY_TOKEN ...`. Programs started afterwards see it.
    macOS/Linux   an `export APIFY_TOKEN=...` line in your shell start-up file (~/.zshrc, ~/.bash_profile
                  or ~/.bashrc), so every new terminal has it.
It is also set for the current run straight away. Reading checks the running environment first, then
the saved value (so a terminal opened before the key was saved still finds it).
The key is never written inside this repository, config.json, the output, or any log.
"""
import os
import re
import sys
from pathlib import Path

NAME = "APIFY_TOKEN"
ENV_NAMES = ("APIFY_TOKEN", "APIFY_API_TOKEN", "APIFY_API_KEY")
IS_WINDOWS = os.name == "nt"
BLOCK_START = "# >>> jobsearch: Apify API key >>>"
BLOCK_END = "# <<< jobsearch <<<"


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
def profile_file():
    """The start-up file your terminal reads: ~/.zshrc for zsh (the macOS default), else bash's."""
    home = Path(os.environ.get("JOBSEARCH_PROFILE_HOME") or Path.home())
    shell = os.path.basename(os.environ.get("SHELL", "") or ("zsh" if sys.platform == "darwin" else "bash"))
    if shell == "zsh":
        return home / ".zshrc"
    if shell == "bash":
        return home / (".bash_profile" if sys.platform == "darwin" else ".bashrc")
    return home / ".profile"


def _block_re():
    return re.compile(rf"\n?{re.escape(BLOCK_START)}\n.*?{re.escape(BLOCK_END)}\n?", re.S)


def _unix_get(name):
    candidates = [profile_file()] + [Path(os.environ.get("JOBSEARCH_PROFILE_HOME") or Path.home()) / f
                                     for f in (".zshrc", ".zprofile", ".bash_profile", ".bashrc", ".profile")]
    for f in dict.fromkeys(candidates):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in re.finditer(rf"^\s*export\s+{name}=(['\"]?)([^'\"\s#]+)\1", text, re.M):
            return m.group(2)
    return None


def _unix_set(name, value):
    f = profile_file()
    old = f.read_text(encoding="utf-8") if f.is_file() else ""
    body = _block_re().sub("\n", old).rstrip("\n")
    safe = value.replace("'", "")
    block = f"{BLOCK_START}\nexport {name}='{safe}'\n{BLOCK_END}\n"
    f.write_text((body + "\n\n" if body else "") + block, encoding="utf-8")


def _unix_delete(name):
    f = profile_file()
    if not f.is_file():
        return False
    old = f.read_text(encoding="utf-8")
    new = _block_re().sub("\n", old)
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


def where_saved():
    """Where the key is kept, in words, for messages."""
    if IS_WINDOWS:
        return f"the {NAME} environment variable (your Windows user variables)"
    return f"the {NAME} environment variable (in ~/{profile_file().name})"


# ---------------------------------------------------------------- public
def save(token):
    """Save the key as APIFY_TOKEN for good, and for this run. Returns where it was saved."""
    persist_set(NAME, token)
    os.environ[NAME] = token
    return where_saved()


def forget():
    """Remove the saved APIFY_TOKEN. Returns True if there was one."""
    removed = persist_delete(NAME)
    if os.environ.pop(NAME, None):
        removed = True
    return bool(removed)


def find():
    """(key, where it came from): the running environment first, then the saved variable."""
    for name in ENV_NAMES:
        val = os.environ.get(name, "").strip()
        if val:
            return val, f"the {name} environment variable"
    for name in ENV_NAMES:
        try:
            val = persist_get(name)
        except Exception:
            val = None
        if val:
            os.environ[name] = val  # this run can use it right away
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
