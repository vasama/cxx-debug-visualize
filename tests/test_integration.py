# End-to-end tests of cxx-debug-visualize against the real debug adapter.
#
# Run through `python3 -m tests` (e.g. by CTest), which passes the built fixture program
# test_program.cpp (--program) and the executables to test with (--gdb, --lldb-dap, --vs-adapter).
# A test class is skipped, and left out of --list, unless every executable it uses was given, and
# fails without the fixture program.

import contextlib
import io
import os
import subprocess
import unittest

from cxx_debug_visualize.runner import Runner

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
SOURCE = os.path.join(FIXTURES, "test_program.cpp")


# Set from the command line by tests/__main__.py: the path of the built fixture program, and
# the full paths of the executables to test with, by option name (None if not given).
PROGRAM = None
TOOLS = {"gdb": None, "lldb-dap": None, "vs-adapter": None}


# Runs cxx-debug-visualize on the fixture program; the test classes below say which debug adapter
# to use.
class FixtureTestCase(unittest.TestCase):
    # path of OpenDebugAD7, or None for the debugger's own DAP support (the default)
    adapter = None
    debugger = "gdb"
    # the executables the tests use, as keys of TOOLS
    tools = ()

    # The options of the executables the tests use that were not given; none if they are to run.
    @classmethod
    def missing(cls):
        return [f"--{tool}" for tool in cls.tools if not TOOLS[tool]]

    @classmethod
    def setUpClass(cls):
        if cls.missing():
            raise unittest.SkipTest("needs " + " ".join(cls.missing()))
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
            debugger_path=TOOLS["gdb" if self.debugger == "gdb" else "lldb-dap"],
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
    tools = ("vs-adapter", "gdb")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.adapter = TOOLS["vs-adapter"]

    def test_good_natvis(self):
        output, errors = self.run_visualizer(natvis="good.natvis")
        self.assertEqual(
            output,
            "\n".join(
                [
                    "visualize(pr) at test_program.cpp:34",
                    "  <1,2> [pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    "visualize(arr) at test_program.cpp:41",
                    "  {...} [int_array]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    # every hit of the call in the loop is printed
                    "visualize(pr) at test_program.cpp:50",
                    "  <0,2> [pair]",
                    "    a = 0 [int]",
                    "    b = 2 [int]",
                    "visualize(pr) at test_program.cpp:50",
                    "  <1,2> [pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    # children that are visualized objects are not expanded
                    "visualize(pa) at test_program.cpp:64",
                    "  {...} [pair_array]",
                    "    [0] = <3,4> [pair]",
                    "    [1] = <5,6> [pair]",
                    # [More...] pages, which continue the list, are flattened into it
                    "visualize(big) at test_program.cpp:73",
                    "  {...} [int_array]",
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
        self.assertIn("<1,-var-create: unable to create variable object> [pair]", output)
        self.assertEqual(errors, [])
        # the ArrayItems <Size> is wrong, so the engine silently shows raw members
        self.assertIn("  {...} [int_array]\n    data = ", output)
        self.assertIn("\n    n = 3 [int]\n", output)

    def test_malformed_natvis(self):
        # the engine ignores the file and reports it on the debug console
        output, errors = self.run_visualizer(natvis="malformed.natvis")
        self.assertIn("{...} [pair]", output)
        # passed on verbatim, as the adapter reported it
        self.assertTrue(
            any(e.startswith("[Natvis] [Error]") and "error in XML document" in e for e in errors),
            errors,
        )

    def test_crash(self):
        output, errors = self.run_visualizer("crash", natvis="good.natvis")
        # the crash comes after the last call, so every call has printed
        self.assertTrue(output.startswith("visualize(pr) at test_program.cpp:34\n"), output)
        self.assertIn("visualize(big) at test_program.cpp:73\n", output)
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
                    "visualize(pr) at test_program.cpp:34",
                    "  <1,2> [pair]",
                    "visualize(arr) at test_program.cpp:41",
                    "  n=3 [int_array]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    "visualize(pr) at test_program.cpp:50",
                    "  <0,2> [pair]",
                    "visualize(pr) at test_program.cpp:50",
                    "  <1,2> [pair]",
                    # the "map" display hint names each value by its key
                    "visualize(pa) at test_program.cpp:64",
                    "  pairs=2 [pair_array]",
                    "    [3] = 4 [int]",
                    "    [5] = 6 [int]",
                    # no [More...] paging
                    "visualize(big) at test_program.cpp:73",
                    "  n=120 [int_array]",
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
        self.assertIn("visualize(pr) at test_program.cpp:34\n   [pair]\n", output)
        self.assertIn(
            "visualize(arr) at test_program.cpp:41\n  n=3 [int_array]\nvisualize(pr)", output
        )
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
    tools = ("gdb",)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if (
            subprocess.run(
                [TOOLS["gdb"], "-nx", "-batch", "-ex", "python import gdb.dap"],
                capture_output=True,
                check=False,
            ).returncode
            != 0
        ):
            raise AssertionError("needs gdb 14 or later")

    def test_good_printers(self):
        output, errors = self.run_visualizer(gdb_printers="good_printers.py")
        self.assertEqual(
            output,
            "\n".join(
                [
                    "visualize(pr) at test_program.cpp:34",
                    "  <1,2> [pair]",
                    "visualize(arr) at test_program.cpp:41",
                    "  n=3 [int_array]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    "visualize(pr) at test_program.cpp:50",
                    "  <0,2> [pair]",
                    "visualize(pr) at test_program.cpp:50",
                    "  <1,2> [pair]",
                    # unlike OpenDebugAD7, gdb shows the "map" display hint's keys and values as children
                    "visualize(pa) at test_program.cpp:64",
                    "  pairs=2 [pair_array]",
                    "    key0 = 3 [int]",
                    "    value0 = 4 [int]",
                    "    key1 = 5 [int]",
                    "    value1 = 6 [int]",
                    "visualize(big) at test_program.cpp:73",
                    "  n=120 [int_array]",
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
        self.assertEqual(output, "visualize(pr) at test_program.cpp:34\n")
        self.assertEqual(errors, ["There is no member named c."])

    def test_malformed_printers(self):
        # unlike through OpenDebugAD7, a script that doesn't load passes silently: values show
        # without printers, for the expected output to catch
        output, errors = self.run_visualizer(gdb_printers="malformed_printers.py")
        self.assertIn(
            "visualize(pr) at test_program.cpp:34\n   [pair]\n    a = 1 [int]\n    b = 2 [int]\n",
            output,
        )
        self.assertEqual(errors, [])

    def test_crash(self):
        output, errors = self.run_visualizer("crash", gdb_printers="good_printers.py")
        # the crash comes after the last call, so every call has printed
        self.assertTrue(output.startswith("visualize(pr) at test_program.cpp:34\n"), output)
        self.assertIn("visualize(big) at test_program.cpp:73\n", output)
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("crash", crash[0])


# The lldb formatters through lldb's own DAP server (lldb-dap, or lldb-vscode before LLVM 18).
class LldbTests(FixtureTestCase):
    debugger = "lldb"
    tools = ("lldb-dap",)

    def test_good_formatters(self):
        output, errors = self.run_visualizer(lldb_formatters="good_formatters.py")
        self.assertEqual(
            output,
            "\n".join(
                [
                    # lldb-dap shows a summary after an empty value and a space, and a summary does not
                    # hide the members
                    "visualize(pr) at test_program.cpp:34",
                    "   <1,2> [pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    "visualize(arr) at test_program.cpp:41",
                    "   n=3 [int_array]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    "visualize(pr) at test_program.cpp:50",
                    "   <0,2> [pair]",
                    "    a = 0 [int]",
                    "    b = 2 [int]",
                    "visualize(pr) at test_program.cpp:50",
                    "   <1,2> [pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    # synthetic children named by key, like the gdb "map" display hint in OpenDebugAD7
                    "visualize(pa) at test_program.cpp:64",
                    "   pairs=2 [pair_array]",
                    "    [3] = 4 [int]",
                    "    [5] = 6 [int]",
                    # no paging
                    "visualize(big) at test_program.cpp:73",
                    "   n=120 [int_array]",
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
            r"visualize\(pr\) at test_program.cpp:34\n"
            r"  pair @ 0x[0-9a-f]+ \[pair\]\n    a = 1 \[int\]\n",
        )
        self.assertIn(
            "visualize(arr) at test_program.cpp:41\n   n=3 [int_array]\nvisualize(pr)", output
        )
        self.assertEqual(errors, [])

    def test_malformed_formatters(self):
        # importing the script fails, which lldb-dap only reports on its debug console: values
        # show without formatters, for the expected output to catch
        output, errors = self.run_visualizer(lldb_formatters="malformed_formatters.py")
        self.assertRegex(
            output,
            r"visualize\(arr\) at test_program.cpp:41\n"
            r"  int_array @ 0x[0-9a-f]+ \[int_array\]\n    data = ",
        )
        self.assertEqual(errors, [])

    def test_crash(self):
        output, errors = self.run_visualizer("crash", lldb_formatters="good_formatters.py")
        # the crash comes after the last call, so every call has printed
        self.assertTrue(output.startswith("visualize(pr) at test_program.cpp:34\n"), output)
        self.assertIn("visualize(big) at test_program.cpp:73\n", output)
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("crash", crash[0])
