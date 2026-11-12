"""The colourful terminal UI: banner, step headers, arrow-key menus, a checkbox list with a live
cost line, hidden key entry, and the file picker.

Colours come from `rich` (output) and `prompt_toolkit` (menus). When the program isn't running
in a terminal (tests, scheduled tasks), menus return their default and output is plain text.
Fonts are chosen by your terminal app, not by programs: see the README for using Google Sans Code.
"""
import sys

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

AUTHOR = "Rahul Swargam"
WEBSITE = "https://rahulswargam.online/"
APIFY_KEY_PAGE = "https://console.apify.com/settings/integrations"

BLUE, RED, YELLOW, GREEN = "#4285F4", "#EA4335", "#FBBC05", "#34A853"
PURPLE, MUTED = "#A142F4", "grey58"
STEP_COLOURS = [BLUE, RED, "#F29900", GREEN]

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


def link(url, label=None, style=BLUE):
    """Clickable text in terminals that support links (Windows Terminal, iTerm2, VS Code...)."""
    return Text(label or url, style=f"underline {style} link {url}")


def banner():
    art = "\n".join(_art("JOB SEARCH"))
    title = gradient(art) if console.width >= 84 else gradient("J O B   S E A R C H")
    tagline = Text("Fresh jobs from 14 job boards, ranked against your resume", style="bold")
    sub = Text("LinkedIn · Naukri · Instahyre · Hirist · Wellfound · Upwork · remote boards · company career sites", style=MUTED)
    visit = Text.assemble(("Visit  ", MUTED), link(WEBSITE, WEBSITE.replace("https://", "").rstrip("/") + "  ↗", GREEN))
    heading = Text.assemble((" ✦ Built by ", "bold white"), (AUTHOR, f"bold {YELLOW}"), (" ✦ ", "bold white"))
    console.print()
    console.print(Panel(Group(title, Text(), tagline, sub, Text(), visit), title=heading, title_align="center",
                        subtitle=Text.assemble(("Powered by Apify · ", MUTED), link(WEBSITE, "rahulswargam.online", GREEN)),
                        border_style=BLUE, box=box.ROUNDED, padding=(1, 3), expand=False))


# ---------------------------------------------------------------- printing helpers
def step(n, total, title, colour=None):
    c = colour or STEP_COLOURS[(n - 1) % len(STEP_COLOURS)]
    console.print()
    console.print(Text.assemble((f" STEP {n} OF {total} ", f"bold white on {c}"), ("  " + title, f"bold {c}")))
    console.rule(style=c, characters="─")


def ok(msg):
    console.print(Text.assemble(("  ✔ ", f"bold {GREEN}"), Text.from_markup(msg) if isinstance(msg, str) else msg))


def info(msg):
    console.print(Text.assemble(("  • ", BLUE), Text.from_markup(msg) if isinstance(msg, str) else msg))


def warn(msg):
    console.print(Text.assemble(("  ! ", "bold #F29900"), Text.from_markup(msg) if isinstance(msg, str) else msg))


def error(msg):
    console.print(Text.assemble(("  ✘ ", f"bold {RED}"), Text.from_markup(msg) if isinstance(msg, str) else msg))


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
    return Application(layout=Layout(Window(FormattedTextControl(render, focusable=True), always_hide_cursor=True, wrap_lines=False)),
                       key_bindings=kb, style=Style.from_dict(PT_STYLE), full_screen=False, erase_when_done=erase, mouse_support=False)


def _common_keys(kb):
    @kb.add("c-c")
    def _(e):
        e.app.exit(exception=KeyboardInterrupt())

    @kb.add("escape")
    def _(e):
        e.app.exit(exception=Cancelled())


def select(question, options, default=0, answer_label=None):
    """Arrow-key menu. options: list of labels or (label, description). Returns the chosen index."""
    opts = [o if isinstance(o, tuple) else (o, "") for o in options]
    if not interactive():
        return default
    from prompt_toolkit.key_binding import KeyBindings
    cur = [max(0, min(default, len(opts) - 1))]
    kb = KeyBindings()
    _common_keys(kb)

    @kb.add("up")
    @kb.add("k")
    def _(e):
        cur[0] = (cur[0] - 1) % len(opts)

    @kb.add("down")
    @kb.add("j")
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

    def render():
        out = [("class:qmark", "  ? "), ("class:q", question + "\n")]
        for i, (label, desc) in enumerate(opts):
            here = i == cur[0]
            out += [("class:pointer" if here else "", "   ❯ " if here else "     "),
                    ("class:sel" if here else "class:opt", f"{i + 1}. {label}")]
            if desc:
                out.append(("class:desc", f"   {desc}"))
            out.append(("", "\n"))
        out.append(("class:hint", "     ↑/↓ to move · Enter to choose · or press the number"))
        return out

    choice = _app(render, kb).run()
    console.print(Text.assemble(("  ✔ ", f"bold {GREEN}"), (question + " ", "bold"),
                                (answer_label or opts[choice][0], f"bold {BLUE}")))
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
        k = order[cur[0]]
        sel.symmetric_difference_update({k})
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
        out = [("class:qmark", "  ? "), ("class:q", question + "\n"),
               ("class:hint", "     ↑/↓ move · Space tick or untick · A tick all · N clear · Enter continue\n\n"),
               ("class:head", "         " + "  ".join(cell(h, w, al) for h, w, al, _ in columns) + "\n")]
        for i, (key, cells, note) in enumerate(rows):
            here, on = i == cur[0], key in sel
            out += [("class:pointer" if here else "", "   ❯ " if here else "     "),
                    ("class:on" if on else "class:off", "◉  " if on else "○  ")]
            for (h, w, al, style), c in zip(columns, cells):
                st = "class:rowcur" if here else ""
                if style:
                    st = f"{st} class:{style}".strip()
                out.append((st, cell(c, w, al) + "  "))
            if note:
                out.append(("class:tag", note))
            out.append(("", "\n"))
        out.append(("", "\n"))
        out.extend(footer([k for k in order if k in sel]))
        if msg[0]:
            out += [("", "\n"), ("class:bad", msg[0])]
        return out

    chosen = _app(render, kb).run()
    console.print(Text.assemble(("  ✔ ", f"bold {GREEN}"), (question + " ", "bold"),
                                (answer(chosen) if answer else ", ".join(chosen), f"bold {BLUE}")))
    return chosen


def secret(message):
    """Hidden entry (shown as dots). Returns the stripped text."""
    from prompt_toolkit import prompt
    from prompt_toolkit.styles import Style
    return prompt([("class:qmark", "  ? "), ("class:q", message)], is_password=True,
                  style=Style.from_dict(PT_STYLE)).strip()


def ask_text(message, default=""):
    if not interactive():
        return default
    from prompt_toolkit import prompt
    from prompt_toolkit.styles import Style
    return prompt([("class:qmark", "  ? "), ("class:q", message + " ")], default=default or "",
                  style=Style.from_dict(PT_STYLE)).strip() or default


def pick_file(title="Choose your resume", initialdir=None):
    """Open the system file window. Returns the chosen path, '' if cancelled, None if no window can open."""
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError:
        return None
    try:
        root = tkinter.Tk()
    except Exception:  # no display (SSH, server)
        return None
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        chosen = filedialog.askopenfilename(parent=root, title=title, initialdir=initialdir or None, filetypes=[
            ("Resume (PDF, Word, text)", "*.pdf *.docx *.txt *.md"), ("All files", "*.*")])
        return chosen or ""
    finally:
        root.destroy()


# ---------------------------------------------------------------- tables
def table(*headers, title=None, colour=BLUE):
    t = Table(box=box.SIMPLE_HEAD, header_style=f"bold {colour}", title=title, title_style="bold", title_justify="left",
              pad_edge=False, show_edge=False)
    for h in headers:
        if isinstance(h, tuple):
            t.add_column(h[0], justify=h[1], style=h[2] if len(h) > 2 else None, no_wrap=True)
        else:
            t.add_column(h, no_wrap=True)
    return t
