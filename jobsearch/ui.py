"""The colourful terminal UI: banner, step headers, arrow-key menus, a checkbox list with a live
cost line, hidden key entry, and the file and folder pickers. Works on Windows and macOS.

Colours come from `rich` (output) and `prompt_toolkit` (menus). When the program isn't running
in a terminal (tests, scheduled tasks), menus return their default and output is plain text.
Fonts are chosen by your terminal app, not by programs: see the README for using Google Sans Code.
"""
import os
import subprocess
import sys
from pathlib import Path

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

AUTHOR = "Rahul Swargam"
WEBSITE = "https://rahulswargam.online/"
APIFY_KEY_PAGE = "https://console.apify.com/settings/integrations"
IS_MAC = sys.platform == "darwin"
IS_WINDOWS = os.name == "nt"

BLUE, RED, YELLOW, GREEN = "#4285F4", "#EA4335", "#FBBC05", "#34A853"
PURPLE, MUTED = "#A142F4", "grey58"
STEP_COLOURS = [BLUE, RED, "#F29900", GREEN, PURPLE]

console = Console(highlight=False)

PT_STYLE = {
    "qmark": f"bold {BLUE}", "q": "bold", "pointer": f"bold {BLUE}", "sel": f"bold {BLUE}", "opt": "",
    "desc": "#9aa0a6", "hint": "italic #9aa0a6", "on": f"bold {GREEN}", "off": "#80868b", "head": "bold #9aa0a6",
    "cost": "#f29900", "ok": f"bold {GREEN}", "warn": "bold #f29900", "bad": f"bold {RED}", "rowcur": "bold",
    "tag": f"{RED}",
}


def interactive():
    return sys.stdin.isatty() and sys.stdout.isatty()


# ---------------------------------------------------------------- banner
_LETTERS = {
    "J": ["     ██╗", "     ██║", "     ██║", "██   ██║", "╚█████╔╝", " ╚════╝ "],
    "O": [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "B": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██████╔╝", "╚═════╝ "],
    "S": ["███████╗", "██╔════╝", "███████╗", "╚════██║", "███████║", "╚══════╝"],
    "E": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"],
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "R": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██║  ██║", "╚═╝  ╚═╝"],
    "C": [" ██████╗", "██╔════╝", "██║     ", "██║     ", "╚██████╗", " ╚═════╝"],
    "H": ["██╗  ██╗", "██║  ██║", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    " ": ["   "] * 6,
}


def _art(word):
    return ["".join(_LETTERS[c][row] for c in word) for row in range(6)]


def _mix(a, b, t):
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def gradient(text, colours=(BLUE, PURPLE, RED, YELLOW, GREEN), bold=True):
    """Colour a line (or block) left to right across the given colours."""
    lines = text.split("\n")
    width = max(len(l) for l in lines) or 1
    out = Text()
    for n, line in enumerate(lines):
        for i, ch in enumerate(line):
            pos = i / max(1, width - 1) * (len(colours) - 1)
            k = min(int(pos), len(colours) - 2)
            out.append(ch, style=f"{'bold ' if bold else ''}{_mix(colours[k], colours[k + 1], pos - k)}")
        if n < len(lines) - 1:
            out.append("\n")
    return out


def link(url, label, style=BLUE):
    """Text that opens `url` when clicked, in terminals that support links."""
    return Text(label, style=f"underline {style} link {url}")


def website_link():
    return link(WEBSITE, "Visit my website ↗", GREEN)


def banner():
    art = "\n".join(_art("JOB SEARCH"))
    title = gradient(art) if console.width >= 90 else gradient("J O B   S E A R C H")
    body = Group(
        Align.center(title), Text(),
        Align.center(Text("Fresh jobs from 14 job boards, ranked against your resume", style="bold")),
        Align.center(Text("LinkedIn · Naukri · Instahyre · Hirist · Wellfound · Upwork · remote boards · company career sites", style=MUTED)),
    )
    heading = Text.assemble((" ✦ Built by ", "bold"), (AUTHOR, f"bold {YELLOW}"), (" ✦ ", "bold"))
    footer = Text.assemble((" Powered by Apify  ·  ", MUTED), website_link(), (" ", ""))
    console.print()
    console.print(Align.center(Panel(body, title=heading, title_align="center", subtitle=footer, subtitle_align="center",
                                     border_style=BLUE, box=box.ROUNDED, padding=(1, 4), expand=False)))
    console.print()


def credit_footer():
    console.print()
    console.print(Align.center(Text.assemble(("Built by ", MUTED), (AUTHOR, f"bold {YELLOW}"), ("   ·   ", MUTED), website_link())))
    console.print()


# ---------------------------------------------------------------- printing helpers
def step(n, total, title, colour=None):
    c = colour or STEP_COLOURS[(n - 1) % len(STEP_COLOURS)]
    console.print()
    console.print()
    console.print(Text.assemble((f" STEP {n} OF {total} ", f"bold white on {c}"), ("   " + title, f"bold {c}")))
    console.rule(style=c, characters="─")
    console.print()


def _line(mark, colour, msg):
    console.print(Text.assemble((f"  {mark}  ", f"bold {colour}"), Text.from_markup(msg) if isinstance(msg, str) else msg))


def ok(msg):
    _line("✔", GREEN, msg)


def info(msg):
    _line("•", BLUE, msg)


def warn(msg):
    _line("!", "#F29900", msg)


def error(msg):
    _line("✘", RED, msg)


def gap():
    console.print()


def money(x):
    if x is None:
        return "-"
    if x >= 0.995 or x == 0 or abs(x * 100 - round(x * 100)) < 1e-9:
        return f"${x:.2f}"
    return f"${x:.3f}" if x >= 0.01 else f"${x:.4f}"


# ---------------------------------------------------------------- interactive widgets
class Cancelled(Exception):
    pass


def _app(render, kb, erase=True):
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
    return Application(layout=Layout(Window(FormattedTextControl(render, focusable=True), always_hide_cursor=True, wrap_lines=True)),
                       key_bindings=kb, style=Style.from_dict(PT_STYLE), full_screen=False, erase_when_done=erase, mouse_support=False)


def _common_keys(kb):
    @kb.add("c-c")
    def _(e):
        e.app.exit(exception=KeyboardInterrupt())

    @kb.add("escape")
    def _(e):
        e.app.exit(exception=Cancelled())


def _answered(question, answer):
    console.print(Text.assemble(("  ✔  ", f"bold {GREEN}"), (question + "  ", "bold"), (answer, f"bold {BLUE}")))
    console.print()


def select(question, options, default=0, answer_label=None):
    """Arrow-key menu. options: labels or (label, description). Returns the chosen index."""
    opts = [o if isinstance(o, tuple) else (o, "") for o in options]
    if not interactive():
        return default
    from prompt_toolkit.key_binding import KeyBindings
    cur = [max(0, min(default, len(opts) - 1))]
    kb = KeyBindings()
    _common_keys(kb)

    @kb.add("up")
    def _(e):
        cur[0] = (cur[0] - 1) % len(opts)

    @kb.add("down")
    @kb.add("tab")
    def _(e):
        cur[0] = (cur[0] + 1) % len(opts)

    @kb.add("enter")
    def _(e):
        e.app.exit(result=cur[0])

    for n in range(1, min(9, len(opts)) + 1):
        @kb.add(str(n))
        def _(e, n=n):
            e.app.exit(result=n - 1)

    roomy = any(desc for _, desc in opts)

    def render():
        out = [("class:qmark", "  ?  "), ("class:q", question + "\n\n")]
        for i, (label, desc) in enumerate(opts):
            here = i == cur[0]
            out += [("class:pointer" if here else "", "     ❯  " if here else "        "),
                    ("class:sel" if here else "class:opt", f"{i + 1}.  {label}\n")]
            if desc:
                out.append(("class:desc", f"            {desc}\n"))
            if roomy and i < len(opts) - 1:
                out.append(("", "\n"))
        out.append(("class:hint", "\n        ↑/↓ move  ·  Enter choose  ·  or press the number"))
        return out

    choice = _app(render, kb).run()
    _answered(question, answer_label or opts[choice][0])
    return choice


def checkbox(question, columns, rows, selected, footer, min_selected=1, answer=None):
    """Checkbox list with a live footer.

    columns: [(header, width, align, style)]   rows: [(key, [cell text...], note)]
    selected: keys ticked at the start   footer(keys) -> prompt_toolkit fragments (recomputed on every key)
    Returns the ticked keys in list order."""
    order = [k for k, _, _ in rows]
    if not interactive():
        return [k for k in order if k in selected]
    from prompt_toolkit.key_binding import KeyBindings
    cur, sel, msg = [0], set(selected), [""]
    kb = KeyBindings()
    _common_keys(kb)

    @kb.add("up")
    def _(e):
        cur[0] = (cur[0] - 1) % len(rows)

    @kb.add("down")
    def _(e):
        cur[0] = (cur[0] + 1) % len(rows)

    @kb.add("space")
    @kb.add("right")
    @kb.add("x")
    def _(e):
        sel.symmetric_difference_update({order[cur[0]]})
        msg[0] = ""

    @kb.add("a")
    def _(e):
        sel.update(order)
        msg[0] = ""

    @kb.add("n")
    def _(e):
        sel.clear()

    @kb.add("enter")
    def _(e):
        if len(sel) < min_selected:
            msg[0] = "  Tick at least one source with Space."
            return
        e.app.exit(result=[k for k in order if k in sel])

    def cell(text, width, align):
        text = str(text)[:width]
        return text.rjust(width) if align == "right" else text.ljust(width)

    def render():
        out = [("class:qmark", "  ?  "), ("class:q", question + "\n"),
               ("class:hint", "     ↑/↓ move  ·  Space tick or untick  ·  A tick all  ·  N clear  ·  Enter continue\n\n"),
               ("class:head", "          " + "   ".join(cell(h, w, al) for h, w, al, _ in columns) + "\n")]
        for i, (key, cells, note) in enumerate(rows):
            here, on = i == cur[0], key in sel
            out += [("class:pointer" if here else "", "     ❯  " if here else "        "),
                    ("class:on" if on else "class:off", "◉  " if on else "○  ")]
            for (h, w, al, style), c in zip(columns, cells):
                st = "class:rowcur" if here else ""
                if style:
                    st = f"{st} class:{style}".strip()
                out.append((st, cell(c, w, al) + "   "))
            if note:
                out.append(("class:tag", note))
            out.append(("", "\n"))
        out.append(("", "\n"))
        out.extend(footer([k for k in order if k in sel]))
        if msg[0]:
            out += [("", "\n"), ("class:bad", msg[0])]
        return out

    chosen = _app(render, kb).run()
    _answered(question, answer(chosen) if answer else ", ".join(chosen))
    return chosen


def secret(message):
    """Hidden entry (shown as dots). Returns the stripped text."""
    from prompt_toolkit import prompt
    from prompt_toolkit.styles import Style
    return prompt([("class:qmark", "  ?  "), ("class:q", message)], is_password=True,
                  style=Style.from_dict(PT_STYLE)).strip()


def ask_text(message, default=""):
    if not interactive():
        return default
    from prompt_toolkit import prompt
    from prompt_toolkit.styles import Style
    return prompt([("class:qmark", "  ?  "), ("class:q", message + " ")], default=default or "",
                  style=Style.from_dict(PT_STYLE)).strip() or default


# ---------------------------------------------------------------- file and folder windows (Windows + macOS)
RESUME_EXTS = ("pdf", "docx", "txt", "md")


def _osascript(script):
    """Run AppleScript; returns its output, '' if the user cancelled, None if it can't run."""
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return "" if "-128" in r.stderr or "cancel" in r.stderr.lower() else None
    return r.stdout.strip()


def _as_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _tk():
    try:
        import tkinter
        root = tkinter.Tk()
    except Exception:  # no Tk, or no display
        return None
    root.withdraw()
    root.attributes("-topmost", True)
    root.update()
    return root


def pick_file(title="Choose your resume", initialdir=None):
    """Open the system file window. Returns the chosen path, '' if cancelled, None if no window can open."""
    if IS_MAC:
        where = f" default location (POSIX file {_as_str(initialdir)})" if initialdir and Path(initialdir).is_dir() else ""
        types = ", ".join(f'"{e}"' for e in RESUME_EXTS)  # filename extensions work as types on macOS
        got = _osascript(f"POSIX path of (choose file with prompt {_as_str(title)} of type {{{types}}}{where})")
        if got is not None:
            return got
    root = _tk()
    if root is None:
        return None
    try:
        from tkinter import filedialog
        chosen = filedialog.askopenfilename(parent=root, title=title, initialdir=initialdir or None, filetypes=[
            ("Resume (PDF, Word, text)", " ".join(f"*.{e}" for e in RESUME_EXTS)), ("All files", "*.*")])
        return chosen or ""
    finally:
        root.destroy()


def pick_folder(title="Choose where to save the job links page", initialdir=None):
    """Open the system folder window. Returns the folder, '' if cancelled, None if no window can open."""
    if IS_MAC:
        where = f" default location (POSIX file {_as_str(initialdir)})" if initialdir and Path(initialdir).is_dir() else ""
        got = _osascript(f"POSIX path of (choose folder with prompt {_as_str(title)}{where})")
        if got is not None:
            return got.rstrip("/") or got
    root = _tk()
    if root is None:
        return None
    try:
        from tkinter import filedialog
        start = initialdir if initialdir and Path(initialdir).is_dir() else None
        chosen = filedialog.askdirectory(parent=root, title=title, initialdir=start, mustexist=False)
        return str(Path(chosen)) if chosen else ""
    finally:
        root.destroy()


def downloads_dir():
    """The user's Downloads folder (follows a moved Downloads folder on Windows)."""
    if IS_WINDOWS:
        try:
            import ctypes
            from ctypes import wintypes
            import uuid

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

            u = uuid.UUID("{374DE290-123F-4565-9164-39C4925E467B}")  # FOLDERID_Downloads
            g = GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8).from_buffer_copy(u.bytes[8:]))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out)) == 0:
                path = out.value
                ctypes.windll.ole32.CoTaskMemFree(out)
                if path:
                    return Path(path)
        except Exception:
            pass
    return Path.home() / "Downloads"


def open_path(path):
    """Show a folder (or open a file) in Explorer / Finder."""
    try:
        if IS_WINDOWS:
            os.startfile(str(path))  # noqa: S606 - opening the user's own folder
        elif IS_MAC:
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except (OSError, AttributeError):
        pass


# ---------------------------------------------------------------- tables
def indent(renderable, left=2):
    """Line a table up with the rest of the text."""
    from rich.padding import Padding
    return Padding(renderable, (0, 0, 0, left))


def table(*headers, title=None, colour=BLUE):
    t = Table(box=box.SIMPLE_HEAD, header_style=f"bold {colour}", title=title, title_style="bold", title_justify="left",
              pad_edge=False, show_edge=False, padding=(0, 2))
    for h in headers:
        if isinstance(h, tuple):
            t.add_column(h[0], justify=h[1], style=h[2] if len(h) > 2 else None, no_wrap=True)
        else:
            t.add_column(h, no_wrap=True)
    return t
