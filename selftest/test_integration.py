# End-to-end tests of cxx-debug-visualize against the real debug adapter.
#
# Run through `python3 -m selftest` (e.g. by CTest), which passes the built fixture program
# test_program.cpp (--program) and the adapter (--vs-adapter). A test class is skipped if
# the debugger or adapter it tests is turned off (--no-vs, --no-gdb, --no-lldb), and otherwise
# fails if what it needs is missing: the program, the adapter, gdb, or lldb-dap.

import contextlib
import io
import os
import shutil
import subprocess
import unittest

from cxx_debug_visualize.adapter import find_lldb_dap
from cxx_debug_visualize.runner import Runner

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
SOURCE = os.path.join(FIXTURES, "test_program.cpp")


# Set from the command line by selftest/__main__.py: the paths of OpenDebugAD7 and of the built
# fixture program, and whether to test the Visual Studio debug adapter, gdb and lldb.
ADAPTER = None
PROGRAM = None
VS = True
GDB = True
LLDB = True


# Runs cxx-debug-visualize on the fixture program; the test classes below say which debug adapter
# to use.
class FixtureTestCase(unittest.TestCase):
    # path of OpenDebugAD7, or None for the debugger's own DAP support (the default)
    adapter = None
    debugger = "gdb"

    @classmethod
    def setUpClass(cls):
        if not PROGRAM:
            raise AssertionError("needs the fixture program (--program)")

    # Run the fixture with a natvis file, a pretty-printer script or an lldb formatter script
    # from fixtures/, and the command line arguments `program_args` (any make it crash at the
    # end); return (stdout, stderr lines).
    def run_visualizer(self, *program_args, natvis=None, gdb_printers=None, lldb_formatters=None):
        fixture = lambda name: name and os.path.join(FIXTURES, name)
        runner = Runner(
            self.adapter,
            SOURCE,
            PROGRAM,
            list(program_args),
            debugger=self.debugger,
            natvis=fixture(natvis),
            gdb_printers=fixture(gdb_printers),
            lldb_formatters=fixture(lldb_formatters),
        )
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            ok = runner.run()
        errors = err.getvalue().splitlines()
        # anything on stderr (adapter messages, cxx-debug-visualize errors) means failure
        self.assertEqual(ok, not errors, errors)
        return out.getvalue(), errors


class IntegrationTests(FixtureTestCase):
    @classmethod
    def setUpClass(cls):
        if not (VS and GDB):
            raise unittest.SkipTest("--no-vs or --no-gdb")
        if not (ADAPTER and shutil.which("gdb")):
            raise AssertionError("needs --vs-adapter and gdb")
        cls.adapter = ADAPTER
        super().setUpClass()

    def test_good_natvis(self):
        output, errors = self.run_visualizer(natvis="good.natvis")
        self.assertEqual(
            output,
            "\n".join(
                [
                    "visualize(pr) at test_program.cpp:17",
                    "  <1,2> [Pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    "visualize(arr) at test_program.cpp:18",
                    "  {...} [Arr]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    # every hit of the call in the loop is printed
                    "visualize(pr) at test_program.cpp:21",
                    "  <0,2> [Pair]",
                    "    a = 0 [int]",
                    "    b = 2 [int]",
                    "visualize(pr) at test_program.cpp:21",
                    "  <1,2> [Pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    # children that are visualized objects are not expanded
                    "visualize(pa) at test_program.cpp:26",
                    "  {...} [PairArr]",
                    "    [0] = <3,4> [Pair]",
                    "    [1] = <5,6> [Pair]",
                    # [More...] pages, which continue the list, are flattened into it
                    "visualize(big) at test_program.cpp:31",
                    "  {...} [Arr]",
                ]
                + [f"    [{i}] = {i} [int]" for i in range(120)]
                + [
                    "",
                ]
            ),
        )
        self.assertEqual(errors, [])

    def test_bad_natvis(self):
        output, errors = self.run_visualizer(natvis="bad.natvis")
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
        self.assertTrue(
            any(e.startswith("[Natvis] [Error]") and "error in XML document" in e for e in errors),
            errors,
        )

    def test_crash(self):
        output, errors = self.run_visualizer("crash", natvis="good.natvis")
        # the crash comes after the last call, so every call has printed
        self.assertTrue(output.startswith("visualize(pr) at test_program.cpp:17\n"), output)
        self.assertIn("visualize(big) at test_program.cpp:31\n", output)
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("crash", crash[0])

    def test_good_printers(self):
        output, errors = self.run_visualizer(gdb_printers="good_printers.py")
        self.assertEqual(
            output,
            "\n".join(
                [
                    # a printer without children() shows no children
                    "visualize(pr) at test_program.cpp:17",
                    "  <1,2> [Pair]",
                    "visualize(arr) at test_program.cpp:18",
                    "  n=3 [Arr]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    "visualize(pr) at test_program.cpp:21",
                    "  <0,2> [Pair]",
                    "visualize(pr) at test_program.cpp:21",
                    "  <1,2> [Pair]",
                    # the "map" display hint names each value by its key
                    "visualize(pa) at test_program.cpp:26",
                    "  pairs=2 [PairArr]",
                    "    [3] = 4 [int]",
                    "    [5] = 6 [int]",
                    # no [More...] paging
                    "visualize(big) at test_program.cpp:31",
                    "  n=120 [Arr]",
                ]
                + [f"    [{i}] = {i} [int]" for i in range(120)]
                + [
                    "",
                ]
            ),
        )
        self.assertEqual(errors, [])

    def test_bad_printers(self):
        output, errors = self.run_visualizer(gdb_printers="bad_printers.py")
        # exceptions in printers pass silently: the value stays empty and the
        # children are missing, for the expected output to catch
        self.assertIn("visualize(pr) at test_program.cpp:17\n   [Pair]\n", output)
        self.assertIn("visualize(arr) at test_program.cpp:18\n  n=3 [Arr]\nvisualize(pr)", output)
        self.assertEqual(errors, [])

    def test_malformed_printers(self):
        # sourcing the script fails, so the launch fails with gdb's message
        output, errors = self.run_visualizer(gdb_printers="malformed_printers.py")
        self.assertEqual(output, "")
        self.assertTrue(
            any(
                e.startswith("Unable to start debugging.") and "invalid syntax" in e for e in errors
            ),
            errors,
        )


# The pretty printers through gdb's own DAP support (the default), without OpenDebugAD7.
class NativeDapTests(FixtureTestCase):
    @classmethod
    def setUpClass(cls):
        if not GDB:
            raise unittest.SkipTest("--no-gdb")
        if (
            not shutil.which("gdb")
            or subprocess.run(
                ["gdb", "-nx", "-batch", "-ex", "python import gdb.dap"],
                capture_output=True,
                check=False,
            ).returncode
            != 0
        ):
            raise AssertionError("needs gdb 14 or later")
        super().setUpClass()

    def test_good_printers(self):
        output, errors = self.run_visualizer(gdb_printers="good_printers.py")
        self.assertEqual(
            output,
            "\n".join(
                [
                    "visualize(pr) at test_program.cpp:17",
                    "  <1,2> [Pair]",
                    "visualize(arr) at test_program.cpp:18",
                    "  n=3 [Arr]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    "visualize(pr) at test_program.cpp:21",
                    "  <0,2> [Pair]",
                    "visualize(pr) at test_program.cpp:21",
                    "  <1,2> [Pair]",
                    # unlike OpenDebugAD7, gdb shows the "map" display hint's keys and values as children
                    "visualize(pa) at test_program.cpp:26",
                    "  pairs=2 [PairArr]",
                    "    key0 = 3 [int]",
                    "    value0 = 4 [int]",
                    "    key1 = 5 [int]",
                    "    value1 = 6 [int]",
                    "visualize(big) at test_program.cpp:31",
                    "  n=120 [Arr]",
                ]
                + [f"    [{i}] = {i} [int]" for i in range(120)]
                + [
                    "",
                ]
            ),
        )
        self.assertEqual(errors, [])

    def test_bad_printers(self):
        # unlike through OpenDebugAD7, a printer that raises makes gdb fail the evaluation: the
        # run stops there, with gdb's message
        output, errors = self.run_visualizer(gdb_printers="bad_printers.py")
        self.assertEqual(output, "visualize(pr) at test_program.cpp:17\n")
        self.assertEqual(errors, ["There is no member named c."])

    def test_malformed_printers(self):
        # unlike through OpenDebugAD7, a script that doesn't load passes silently: values show
        # without printers, for the expected output to catch
        output, errors = self.run_visualizer(gdb_printers="malformed_printers.py")
        self.assertIn(
            "visualize(pr) at test_program.cpp:17\n   [Pair]\n    a = 1 [int]\n    b = 2 [int]\n",
            output,
        )
        self.assertEqual(errors, [])

    def test_crash(self):
        output, errors = self.run_visualizer("crash", gdb_printers="good_printers.py")
        # the crash comes after the last call, so every call has printed
        self.assertTrue(output.startswith("visualize(pr) at test_program.cpp:17\n"), output)
        self.assertIn("visualize(big) at test_program.cpp:31\n", output)
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("crash", crash[0])


# The lldb formatters through lldb's own DAP server (lldb-dap, or lldb-vscode before LLVM 18).
class LldbTests(FixtureTestCase):
    debugger = "lldb"

    @classmethod
    def setUpClass(cls):
        if not LLDB:
            raise unittest.SkipTest("--no-lldb")
        if not find_lldb_dap():
            raise AssertionError("needs lldb-dap (or lldb-vscode) on PATH")
        super().setUpClass()

    def test_good_formatters(self):
        output, errors = self.run_visualizer(lldb_formatters="good_formatters.py")
        self.assertEqual(
            output,
            "\n".join(
                [
                    # lldb-dap shows a summary after an empty value and a space, and a summary does not
                    # hide the members
                    "visualize(pr) at test_program.cpp:17",
                    "   <1,2> [Pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    "visualize(arr) at test_program.cpp:18",
                    "   n=3 [Arr]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    "visualize(pr) at test_program.cpp:21",
                    "   <0,2> [Pair]",
                    "    a = 0 [int]",
                    "    b = 2 [int]",
                    "visualize(pr) at test_program.cpp:21",
                    "   <1,2> [Pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    # synthetic children named by key, like the gdb "map" display hint in OpenDebugAD7
                    "visualize(pa) at test_program.cpp:26",
                    "   pairs=2 [PairArr]",
                    "    [3] = 4 [int]",
                    "    [5] = 6 [int]",
                    # no paging
                    "visualize(big) at test_program.cpp:31",
                    "   n=120 [Arr]",
                ]
                + [f"    [{i}] = {i} [int]" for i in range(120)]
                + [
                    "",
                ]
            ),
        )
        self.assertEqual(errors, [])

    def test_bad_formatters(self):
        # exceptions in formatters pass silently: a summary falls back to lldb's default and
        # synthetic children are missing, for the expected output to catch
        output, errors = self.run_visualizer(lldb_formatters="bad_formatters.py")
        self.assertRegex(
            output,
            r"visualize\(pr\) at test_program.cpp:17\n"
            r"  Pair @ 0x[0-9a-f]+ \[Pair\]\n    a = 1 \[int\]\n",
        )
        self.assertIn("visualize(arr) at test_program.cpp:18\n   n=3 [Arr]\nvisualize(pr)", output)
        self.assertEqual(errors, [])

    def test_malformed_formatters(self):
        # importing the script fails, which lldb-dap only reports on its debug console: values
        # show without formatters, for the expected output to catch
        output, errors = self.run_visualizer(lldb_formatters="malformed_formatters.py")
        self.assertRegex(
            output,
            r"visualize\(arr\) at test_program.cpp:18\n"
            r"  Arr @ 0x[0-9a-f]+ \[Arr\]\n    data = ",
        )
        self.assertEqual(errors, [])

    def test_crash(self):
        output, errors = self.run_visualizer("crash", lldb_formatters="good_formatters.py")
        # the crash comes after the last call, so every call has printed
        self.assertTrue(output.startswith("visualize(pr) at test_program.cpp:17\n"), output)
        self.assertIn("visualize(big) at test_program.cpp:31\n", output)
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("crash", crash[0])
