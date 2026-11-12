"""Drive the real arrow-key menus with simulated keystrokes (no terminal needed)."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prompt_toolkit.application import create_app_session  # noqa: E402
from prompt_toolkit.input import create_pipe_input  # noqa: E402
from prompt_toolkit.output import DummyOutput  # noqa: E402

from jobsearch import ui  # noqa: E402

DOWN, UP, ENTER = "\x1b[B", "\x1b[A", "\r"


def drive(keys, fn, *args, **kw):
    buf = io.StringIO()
    with create_pipe_input() as inp, create_app_session(input=inp, output=DummyOutput()), \
            mock.patch.object(ui, "interactive", lambda: True), redirect_stdout(buf):
        inp.send_text(keys)
        return fn(*args, **kw), buf.getvalue()


class Widgets(unittest.TestCase):
    def test_select_arrows_and_numbers(self):
        self.assertEqual(drive(DOWN + DOWN + ENTER, ui.select, "Pick", ["a", "b", "c"])[0], 2)
        self.assertEqual(drive(UP + ENTER, ui.select, "Pick", ["a", "b", "c"])[0], 2)  # wraps around
        choice, out = drive("2", ui.select, "Pick", [("First", "x"), ("Second", "y")])
        self.assertEqual(choice, 1)
        self.assertIn("Second", out)  # the answer is echoed after the menu closes

    def test_checkbox_ticks_and_live_footer(self):
        rows = [("a", ["a", "1"], ""), ("b", ["b", "2"], ""), ("c", ["c", "3"], "note")]
        cols = [("key", 5, "left", None), ("n", 3, "right", "cost")]
        seen = []

        def footer(keys):
            seen.append(list(keys))
            return [("", f"{len(keys)} picked")]

        # start with a ticked; untick a, move to c, tick c. (Keys sent in one burst are handled before the next
        # redraw, so only the first frame is checked here; a real terminal redraws after every key.)
        picked, _ = drive(" " + DOWN + DOWN + " " + ENTER, ui.checkbox, "Sources", cols, rows, {"a"}, footer)
        self.assertEqual(picked, ["c"])
        self.assertIn(["a"], seen)        # footer drawn from the ticked keys
        self.assertEqual(drive("a" + ENTER, ui.checkbox, "Sources", cols, rows, set(), footer)[0], ["a", "b", "c"])

    def test_checkbox_needs_one(self):
        rows = [("a", ["a"], ""), ("b", ["b"], "")]
        picked, _ = drive("n" + ENTER + DOWN + " " + ENTER, ui.checkbox, "Sources", [("k", 3, "left", None)], rows, {"a"},
                          lambda k: [])
        self.assertEqual(picked, ["b"])   # the first Enter with nothing ticked was refused

    def test_ctrl_c_stops(self):
        with self.assertRaises(KeyboardInterrupt):
            drive("\x03", ui.select, "Pick", ["a", "b"])

    def test_money(self):
        self.assertEqual([ui.money(x) for x in (0.5, 0.186, 0.0065, 4, None)], ["$0.50", "$0.186", "$0.0065", "$4.00", "-"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
