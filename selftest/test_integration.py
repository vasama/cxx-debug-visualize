# End-to-end tests of cxx-vistest against the real debug adapter.
#
# Run through `python3 -m selftest --adapter PATH`. Each test class is skipped when what it
# needs is missing: the adapter (--adapter), gdb, lldb-dap, or a C++ compiler.

import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest

from cxx_vistest.adapter import find_lldb_dap
from cxx_vistest.runner import Runner

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
SOURCE = os.path.join(FIXTURES, "prog.cpp")


# Path of OpenDebugAD7, set from the command line by selftest/__main__.py.
ADAPTER = None
CXX = os.environ.get("CXX") or shutil.which("g++") or shutil.which("clang++")


# Builds the fixture program and runs cxx-vistest on it; the test classes below say which
# debug adapter to use.
class FixtureTestCase(unittest.TestCase):
    # path of OpenDebugAD7, or None for the debugger's own DAP support (the default)
    adapter = None
    debugger = "gdb"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="cxx-vistest-")
        # variants of the fixture: without and with a crash after the last call
        cls.programs = {}
        for variant, crash in (("plain", 0), ("crash", 1)):
            program = os.path.join(cls.tmp, f"prog_{variant}")
            subprocess.check_call([CXX, "-g", "-O0", f"-DCRASH={crash}",
                                   "-I", os.path.join(HERE, "..", "include"),
                                   "-o", program, SOURCE])
            cls.programs[variant] = program

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # Run the fixture with a natvis file, a pretty-printer script or an lldb formatter script
    # from fixtures/; return (stdout, stderr lines).
    def run_visualizer(self, variant="plain", *, natvis=None, gdb_printers=None,
                       lldb_formatters=None):
        fixture = lambda name: name and os.path.join(FIXTURES, name)
        runner = Runner(self.adapter, self.programs[variant], SOURCE, debugger=self.debugger,
                        natvis=fixture(natvis), gdb_printers=fixture(gdb_printers),
                        lldb_formatters=fixture(lldb_formatters))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            ok = runner.run()
        errors = err.getvalue().splitlines()
        # anything on stderr (adapter messages, cxx-vistest errors) means failure
        self.assertEqual(ok, not errors, errors)
        return out.getvalue(), errors


class IntegrationTests(FixtureTestCase):
    @classmethod
    def setUpClass(cls):
        if not (ADAPTER and CXX and shutil.which("gdb")):
            raise unittest.SkipTest("needs --adapter, gdb and a C++ compiler")
        cls.adapter = ADAPTER
        super().setUpClass()

    def test_good_natvis(self):
        output, errors = self.run_visualizer(natvis="good.natvis")
        self.assertEqual(output, "\n".join([
            "visualize(pr) at prog.cpp:17",
            "  <1,2> [Pair]",
            "    a = 1 [int]",
            "    b = 2 [int]",
            "visualize(arr) at prog.cpp:18",
            "  {...} [Arr]",
            "    [0] = 7 [int]",
            "    [1] = 8 [int]",
            "    [2] = 9 [int]",
            # every hit of the call in the loop is printed
            "visualize(pr) at prog.cpp:21",
            "  <0,2> [Pair]",
            "    a = 0 [int]",
            "    b = 2 [int]",
            "visualize(pr) at prog.cpp:21",
            "  <1,2> [Pair]",
            "    a = 1 [int]",
            "    b = 2 [int]",
            # children that are visualized objects are not expanded
            "visualize(pa) at prog.cpp:26",
            "  {...} [PairArr]",
            "    [0] = <3,4> [Pair]",
            "    [1] = <5,6> [Pair]",
            # [More...] pages, which continue the list, are flattened into it
            "visualize(big) at prog.cpp:31",
            "  {...} [Arr]",
        ] + [f"    [{i}] = {i} [int]" for i in range(120)] + [
            "",
        ]))
        self.assertEqual(errors, [])

    def test_evaluation_errors(self):
        output, errors = self.run_visualizer(natvis="bad_expr.natvis")
        # the DisplayString refers to a missing member: the engine's error text
        # appears in place of the value, for the expected output to catch
        self.assertIn("<1,-var-create: unable to create variable object> [Pair]", output)
        self.assertEqual(errors, [])
        # the ArrayItems <Size> is wrong, so the engine silently shows raw members
        self.assertIn("  {...} [Arr]\n    data = ", output)
        self.assertIn("\n    n = 3 [int]\n", output)

    def test_malformed_natvis(self):
        # the engine ignores the file and reports it on the debug console
        output, errors = self.run_visualizer(natvis="malformed.natvis")
        self.assertIn("{...} [Pair]", output)
        # passed on verbatim, as the adapter reported it
        self.assertTrue(any(e.startswith("[Natvis] [Error]") and "error in XML document" in e
                            for e in errors), errors)

    def test_crash(self):
        output, errors = self.run_visualizer("crash", natvis="good.natvis")
        # the crash comes after the last call, so every call has printed
        self.assertTrue(output.startswith("visualize(pr) at prog.cpp:17\n"), output)
        self.assertIn("visualize(big) at prog.cpp:31\n", output)
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("crash", crash[0])

    def test_good_printers(self):
        output, errors = self.run_visualizer(gdb_printers="good_printers.py")
        self.assertEqual(output, "\n".join([
            # a printer without children() shows no children
            "visualize(pr) at prog.cpp:17",
            "  <1,2> [Pair]",
            "visualize(arr) at prog.cpp:18",
            "  n=3 [Arr]",
            "    [0] = 7 [int]",
            "    [1] = 8 [int]",
            "    [2] = 9 [int]",
            "visualize(pr) at prog.cpp:21",
            "  <0,2> [Pair]",
            "visualize(pr) at prog.cpp:21",
            "  <1,2> [Pair]",
            # the "map" display hint names each value by its key
            "visualize(pa) at prog.cpp:26",
            "  pairs=2 [PairArr]",
            "    [3] = 4 [int]",
            "    [5] = 6 [int]",
            # no [More...] paging
            "visualize(big) at prog.cpp:31",
            "  n=120 [Arr]",
        ] + [f"    [{i}] = {i} [int]" for i in range(120)] + [
            "",
        ]))
        self.assertEqual(errors, [])

    def test_printer_errors(self):
        output, errors = self.run_visualizer(gdb_printers="broken_printers.py")
        # exceptions in printers pass silently: the value stays empty and the
        # children are missing, for the expected output to catch
        self.assertIn("visualize(pr) at prog.cpp:17\n   [Pair]\n", output)
        self.assertIn("visualize(arr) at prog.cpp:18\n  n=3 [Arr]\n"
                      "visualize(pr)", output)
        self.assertEqual(errors, [])

    def test_malformed_printers(self):
        # sourcing the script fails, so the launch fails with gdb's message
        output, errors = self.run_visualizer(gdb_printers="malformed_printers.py")
        self.assertEqual(output, "")
        self.assertTrue(any(e.startswith("Unable to start debugging.") and "invalid syntax" in e
                            for e in errors), errors)



# The pretty printers through gdb's own DAP support (the default), without OpenDebugAD7.
class NativeDapTests(FixtureTestCase):
    @classmethod
    def setUpClass(cls):
        if not (CXX and shutil.which("gdb")) or subprocess.run(
                ["gdb", "-nx", "-batch", "-ex", "python import gdb.dap"],
                capture_output=True).returncode != 0:
            raise unittest.SkipTest("needs gdb 14 or later and a C++ compiler")
        super().setUpClass()

    def test_good_printers(self):
        output, errors = self.run_visualizer(gdb_printers="good_printers.py")
        self.assertEqual(output, "\n".join([
            "visualize(pr) at prog.cpp:17",
            "  <1,2> [Pair]",
            "visualize(arr) at prog.cpp:18",
            "  n=3 [Arr]",
            "    [0] = 7 [int]",
            "    [1] = 8 [int]",
            "    [2] = 9 [int]",
            "visualize(pr) at prog.cpp:21",
            "  <0,2> [Pair]",
            "visualize(pr) at prog.cpp:21",
            "  <1,2> [Pair]",
            # unlike OpenDebugAD7, gdb shows the "map" display hint's keys and values as children
            "visualize(pa) at prog.cpp:26",
            "  pairs=2 [PairArr]",
            "    key0 = 3 [int]",
            "    value0 = 4 [int]",
            "    key1 = 5 [int]",
            "    value1 = 6 [int]",
            "visualize(big) at prog.cpp:31",
            "  n=120 [Arr]",
        ] + [f"    [{i}] = {i} [int]" for i in range(120)] + [
            "",
        ]))
        self.assertEqual(errors, [])

    def test_crash(self):
        output, errors = self.run_visualizer("crash", gdb_printers="good_printers.py")
        # the crash comes after the last call, so every call has printed
        self.assertTrue(output.startswith("visualize(pr) at prog.cpp:17\n"), output)
        self.assertIn("visualize(big) at prog.cpp:31\n", output)
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("crash", crash[0])



# The lldb formatters through lldb's own DAP server (lldb-dap, or lldb-vscode before LLVM 18).
class LldbTests(FixtureTestCase):
    debugger = "lldb"

    @classmethod
    def setUpClass(cls):
        if not (CXX and find_lldb_dap()):
            raise unittest.SkipTest("needs lldb-dap (or lldb-vscode) on PATH and a C++ compiler")
        super().setUpClass()

    def test_good_formatters(self):
        output, errors = self.run_visualizer(lldb_formatters="good_formatters.py")
        self.assertEqual(output, "\n".join([
            # lldb-dap shows a summary after an empty value and a space, and a summary does not
            # hide the members
            "visualize(pr) at prog.cpp:17",
            "   <1,2> [Pair]",
            "    a = 1 [int]",
            "    b = 2 [int]",
            "visualize(arr) at prog.cpp:18",
            "   n=3 [Arr]",
            "    [0] = 7 [int]",
            "    [1] = 8 [int]",
            "    [2] = 9 [int]",
            "visualize(pr) at prog.cpp:21",
            "   <0,2> [Pair]",
            "    a = 0 [int]",
            "    b = 2 [int]",
            "visualize(pr) at prog.cpp:21",
            "   <1,2> [Pair]",
            "    a = 1 [int]",
            "    b = 2 [int]",
            # synthetic children named by key, like the gdb "map" display hint in OpenDebugAD7
            "visualize(pa) at prog.cpp:26",
            "   pairs=2 [PairArr]",
            "    [3] = 4 [int]",
            "    [5] = 6 [int]",
            # no paging
            "visualize(big) at prog.cpp:31",
            "   n=120 [Arr]",
        ] + [f"    [{i}] = {i} [int]" for i in range(120)] + [
            "",
        ]))
        self.assertEqual(errors, [])

    def test_crash(self):
        output, errors = self.run_visualizer("crash", lldb_formatters="good_formatters.py")
        # the crash comes after the last call, so every call has printed
        self.assertTrue(output.startswith("visualize(pr) at prog.cpp:17\n"), output)
        self.assertIn("visualize(big) at prog.cpp:31\n", output)
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("crash", crash[0])


if __name__ == "__main__":
    unittest.main()
