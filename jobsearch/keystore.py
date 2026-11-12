"""Register your Apify API key once; it is kept by your operating system, never in this project.

    Windows   Windows Credential Manager  (Control Panel > Credential Manager > Windows Credentials)
    macOS     Keychain                    (Keychain Access, search "jobsearch")
    Linux     Secret Service when available

If no system store is available, it falls back to a file readable only by you, in
%APPDATA%\\jobsearch (encrypted with Windows DPAPI) or ~/.config/jobsearch. The key is never
written inside the repository, config.json, the output, or any log.
"""
import base64
import json
import os
import sys
from pathlib import Path

SERVICE = "jobsearch-apify"
ACCOUNT = "api-key"
ENV_NAMES = ("APIFY_TOKEN", "APIFY_API_TOKEN", "APIFY_API_KEY")


# ---------------------------------------------------------------- where it lives
def _use_file():
    return os.environ.get("JOBSEARCH_KEYSTORE") == "file"


def _keyring():
    if _use_file():
        return None
    try:
        import keyring
        from keyring.backends import fail
        kr = keyring.get_keyring()
        if isinstance(kr, fail.Keyring) or "null" in type(kr).__name__.lower():
            return None
        return keyring
    except Exception:  # not installed, or no usable backend (headless Linux)
        return None


def store_name():
    """Human name of where the key is kept, for messages."""
    if _keyring():
        return {"win32": "Windows Credential Manager", "darwin": "macOS Keychain"}.get(sys.platform, "your system keyring")
    return f"{_file()} (only your account can read it)"


def app_dir():
    override = os.environ.get("JOBSEARCH_HOME")
    if override:
        return Path(override)
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "jobsearch"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "jobsearch"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "jobsearch"


def _file():
    return app_dir() / "apify-key.json"


# ---------------------------------------------------------------- Windows DPAPI (file fallback only)
def _dpapi(data, encrypt):
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    pb = ctypes.POINTER(Blob)
    crypt32.CryptProtectData.argtypes = [pb, wintypes.LPCWSTR, pb, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, pb]
    crypt32.CryptUnprotectData.argtypes = [pb, ctypes.c_void_p, pb, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, pb]
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    buf = ctypes.create_string_buffer(data, len(data))
    src, out = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), Blob()
    fn = crypt32.CryptProtectData if encrypt else crypt32.CryptUnprotectData
    args = (ctypes.byref(src), "jobsearch" if encrypt else None, None, None, None, 0, ctypes.byref(out))
    if not fn(*args):
        raise OSError("Windows could not protect the key")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


# ---------------------------------------------------------------- public
def save(token):
    """Register the key. Returns where it was kept."""
    kr = _keyring()
    if kr:
        try:
            kr.set_password(SERVICE, ACCOUNT, token)
            return store_name()
        except Exception:
            pass
    p = _file()
    p.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        blob = {"scheme": "dpapi", "key": base64.b64encode(_dpapi(token.encode("utf-8"), True)).decode("ascii")}
    else:
        blob = {"scheme": "plain", "key": token}
    p.write_text(json.dumps(blob), encoding="utf-8")
    if os.name != "nt":
        os.chmod(p, 0o600)
    return f"{p} (only your account can read it)"


def load():
    """The registered key, or None."""
    kr = _keyring()
    if kr:
        try:
            tok = kr.get_password(SERVICE, ACCOUNT)
            if tok:
                return tok
        except Exception:
            pass
    try:
        blob = json.loads(_file().read_text(encoding="utf-8"))
        if blob.get("scheme") == "dpapi":
            return _dpapi(base64.b64decode(blob["key"]), False).decode("utf-8") or None
        return blob.get("key") or None
    except (OSError, ValueError, KeyError):
        return None


def forget():
    """Remove the registered key. Returns True if there was one."""
    removed = False
    kr = _keyring()
    if kr:
        try:
            if kr.get_password(SERVICE, ACCOUNT):
                kr.delete_password(SERVICE, ACCOUNT)
                removed = True
        except Exception:
            pass
    try:
        _file().unlink()
        removed = True
    except OSError:
        pass
    return removed


def from_environment():
    """(key, where) from APIFY_TOKEN-style variables. On Windows this also reads values saved with
    `setx` or System Properties, which terminals opened before the change can't see yet."""
    for name in ENV_NAMES:
        val = os.environ.get(name, "").strip()
        if val:
            return val, f"the {name} environment variable"
    if os.name == "nt":
        try:
            import winreg
            places = ((winreg.HKEY_CURRENT_USER, "Environment"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"))
            for name in ENV_NAMES:
                for root, path in places:
                    try:
                        with winreg.OpenKey(root, path) as k:
                            val = str(winreg.QueryValueEx(k, name)[0] or "").strip()
                        if val:
                            return val, f"the {name} environment variable"
                    except OSError:
                        continue
        except ImportError:
            pass
    return None, None


def find():
    """(key, where it came from) — the registered key first, then environment variables."""
    tok = load()
    if tok:
        return tok, "saved"
    return from_environment()
