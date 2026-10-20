"""End-to-end tests of natvistest against the real debug adapter.

Run through `python3 -m selftest --adapter PATH`; skipped when no adapter is
given, or when gdb or a C++ compiler is missing.
"""

import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest

from natvistest.runner import Runner

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
SOURCE = os.path.join(FIXTURES, "prog.cpp")


# Path of OpenDebugAD7, set from the command line by selftest/__main__.py.
ADAPTER = None
CXX = os.environ.get("CXX") or shutil.which("g++") or shutil.which("clang++")


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ADAPTER and CXX and shutil.which("gdb")):
            raise unittest.SkipTest("needs --adapter, gdb and a C++ compiler")
        cls.tmp = tempfile.mkdtemp(prefix="natvistest-")
        # variants of the fixture, selecting its optional paths at compile time
        cls.programs = {}
        for variant, crash, reach_all in (("plain", 0, 0), ("reach_all", 0, 1), ("crash", 1, 0)):
            program = os.path.join(cls.tmp, f"prog_{variant}")
            subprocess.check_call([CXX, "-g", "-O0", f"-DCRASH={crash}",
                                   f"-DREACH_ALL={reach_all}",
                                   "-I", os.path.join(HERE, "..", "include"),
                                   "-o", program, SOURCE])
            cls.programs[variant] = program

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_natvis(self, natvis, variant="plain"):
        runner = Runner(ADAPTER, self.programs[variant], SOURCE,
                        os.path.join(FIXTURES, natvis))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            ok = runner.run()
        errors = err.getvalue().splitlines()
        # anything on stderr (adapter messages, natvistest errors) means failure
        self.assertEqual(ok, not errors, errors)
        return out.getvalue(), errors

    def test_good_natvis(self):
        output, errors = self.run_natvis("good.natvis")
        self.assertEqual(output, "\n".join([
            "check_visualizer(pr) at prog.cpp:17",
            "  <1,2> [Pair]",
            "    a = 1 [int]",
            "    b = 2 [int]",
            "check_visualizer(arr) at prog.cpp:18",
            "  {...} [Arr]",
            "    [0] = 7 [int]",
            "    [1] = 8 [int]",
            "    [2] = 9 [int]",
            "    [Raw View] = {...}",
            # every hit of the call in the loop is printed
            "check_visualizer(pr) at prog.cpp:21",
            "  <0,2> [Pair]",
            "    a = 0 [int]",
            "    b = 2 [int]",
            "check_visualizer(pr) at prog.cpp:21",
            "  <1,2> [Pair]",
            "    a = 1 [int]",
            "    b = 2 [int]",
            # children that are visualized objects are not expanded
            "check_visualizer(pa) at prog.cpp:30",
            "  {...} [PairArr]",
            "    [0] = <3,4> [Pair]",
            "    [1] = <5,6> [Pair]",
            "    [Raw View] = {...}",
            # [More...] nodes, which continue the list, are followed
            "check_visualizer(big) at prog.cpp:35",
            "  {...} [Arr]",
        ] + [f"    [{i}] = {i} [int]" for i in range(50)] + [
            "    [More...] = {...}",
        ] + [f"      [{i}] = {i} [int]" for i in range(50, 100)] + [
            "      [More...] = {...}",
        ] + [f"        [{i}] = {i} [int]" for i in range(100, 120)] + [
            "    [Raw View] = {...}",
            "",
        ]))
        # the call inside `if (REACH_ALL)` is not reached in this variant: it
        # simply prints nothing (line 27 is absent above), which is not an error
        self.assertEqual(errors, [])

    def test_all_calls_reached(self):
        output, errors = self.run_natvis("good.natvis", variant="reach_all")
        self.assertEqual(errors, [])
        self.assertIn("check_visualizer(pr) at prog.cpp:27\n"
                      "  <1,2> [Pair]\n    a = 1 [int]\n    b = 2 [int]\n"
                      "check_visualizer(pa) at prog.cpp:30\n", output)

    def test_evaluation_errors(self):
        output, errors = self.run_natvis("bad_expr.natvis")
        # the DisplayString refers to a missing member: the engine's error text
        # appears in place of the value, for the CHECK lines to catch
        self.assertIn("<1,-var-create: unable to create variable object> [Pair]", output)
        self.assertEqual(errors, [])
        # the ArrayItems <Size> is wrong, so the engine silently shows raw members
        self.assertIn("  {...} [Arr]\n    data = ", output)
        self.assertIn("\n    n = 3 [int]\n", output)

    def test_malformed_natvis(self):
        # the engine ignores the file and reports it on the debug console
        output, errors = self.run_natvis("malformed.natvis")
        self.assertIn("{...} [Pair]", output)
        # passed on verbatim, as the adapter reported it
        self.assertTrue(any(e.startswith("[Natvis] [Error]") and "error in XML document" in e
                            for e in errors), errors)

    def test_crash(self):
        output, errors = self.run_natvis("good.natvis", variant="crash")
        self.assertTrue(output.startswith("check_visualizer(pr) at prog.cpp:17\n"), output)
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("crash", crash[0])

if __name__ == "__main__":
    unittest.main()
