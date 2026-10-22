# End-to-end tests of cxx-debug-visualize against the real debug adapter.
#
# Run through `python3 -m tests` (e.g. by CTest), which passes the built fixture program
# test_program.cpp (--program) and the executables to test with (--gdb, --lldb-dap, --lldb-mi,
# --miengine, --dbgeng). A test class is skipped, and left out of --list, unless every executable
# it uses was given, and fails without the fixture program.

import contextlib
import io
import os
import re
import subprocess
import unittest

from cxx_debug_visualize.runner import Runner

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
SOURCE = os.path.join(FIXTURES, "test_program.cpp")


# Set from the command line by tests/__main__.py: the path of the built fixture program, and
# the full paths of the executables to test with, by option name (None if not given).
PROGRAM = None
TOOLS = {
    "gdb": None,
    "lldb-dap": None,
    "lldb-mi": None,
    "miengine": None,
    "dbgeng": None,
    "dbgeng-dll": None,
}


# Runs cxx-debug-visualize on the fixture program; the test classes below say which debug adapter
# to use.
class FixtureTestCase(unittest.TestCase):
    # the debug adapter, "miengine" or "dbgeng", and its path; None for the debugger's own DAP
    # support (the default)
    adapter = None
    adapter_path = None
    debugger = "gdb"
    # the executable given as the debugger, as a key of TOOLS
    debugger_tool = "gdb"
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
    # from fixtures/, and the command line arguments `program_args` (see test_program.cpp);
    # return (stdout, stderr lines).
    def run_visualizer(self, *program_args, natvis=None, gdb_printers=None, lldb_formatters=None):
        fixture = lambda name: name and os.path.join(FIXTURES, name)
        runner = Runner(
            self.adapter,
            self.adapter_path,
            SOURCE,
            PROGRAM,
            list(program_args),
            debugger=self.debugger,
            debugger_path=TOOLS[self.debugger_tool],
            natvis=fixture(natvis),
            gdb_printers=fixture(gdb_printers),
            lldb_formatters=fixture(lldb_formatters),
            # only the visualizer under test
            default_visualizers=False,
        )
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            ok = runner.run()
        errors = err.getvalue().splitlines()
        # anything on stderr (adapter messages, cxx-debug-visualize errors) means failure
        self.assertEqual(ok, not errors, errors)
        return out.getvalue(), errors


# The natvis tests through MIEngine (OpenDebugAD7) whose outcome is the same with gdb as with lldb
# (lldb-mi), for the test classes of each.
class MiengineNatvisTests:
    adapter = "miengine"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.adapter_path = TOOLS["miengine"]

    def test_good_natvis(self):
        output, errors = self.run_visualizer(natvis="good.natvis")
        self.assertEqual(
            output,
            "\n".join(
                [
                    "visualize(pr) at test_program.cpp",
                    "  <1,2> [pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    "visualize(arr) at test_program.cpp",
                    "  {...} [int_array]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    # every hit of the call in the loop is printed
                    "visualize(pr) at test_program.cpp",
                    "  <0,2> [pair]",
                    "    a = 0 [int]",
                    "    b = 2 [int]",
                    "visualize(pr) at test_program.cpp",
                    "  <1,2> [pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    # children that are visualized objects are not expanded
                    "visualize(pa) at test_program.cpp",
                    "  {...} [pair_array]",
                    "    [0] = <3,4> [pair]",
                    "    [1] = <5,6> [pair]",
                    # [More...] pages, which continue the list, are flattened into it
                    "visualize(big) at test_program.cpp",
                    "  {...} [int_array]",
                ]
                + [f"    [{i}] = {i} [int]" for i in range(120)]
                + [
                    # a call in another function, on a reference, which MIEngine expands to the
                    # referee's members
                    "visualize(ref) at test_program.cpp",
                    "  <1,2> [const pair &]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    "",
                ]
            ),
        )
        self.assertEqual(errors, [])

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
        output, errors = self.run_visualizer("-c", natvis="good.natvis")
        # the crash comes before any call, so nothing has printed
        self.assertEqual(output, "")
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("main", crash[0])


# natvis files and gdb's pretty printers through MIEngine, with gdb.
class MiengineGdbTests(MiengineNatvisTests, FixtureTestCase):
    tools = ("miengine", "gdb")

    def test_bad_natvis(self):
        output, errors = self.run_visualizer(natvis="bad.natvis")
        # the DisplayString refers to a missing member: the engine's error text
        # appears in place of the value, for the expected output to catch
        self.assertIn("<1,-var-create: unable to create variable object> [pair]", output)
        self.assertEqual(errors, [])
        # the ArrayItems <Size> is wrong, so the engine silently shows raw members
        self.assertIn("  {...} [int_array]\n    data = ", output)
        self.assertIn("\n    n = 3 [int]\n", output)

    def test_good_printers(self):
        output, errors = self.run_visualizer(gdb_printers="good_printers.py")
        self.assertEqual(
            output,
            "\n".join(
                [
                    # a printer without children() shows no children
                    "visualize(pr) at test_program.cpp",
                    "  <1,2> [pair]",
                    "visualize(arr) at test_program.cpp",
                    "  n=3 [int_array]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    "visualize(pr) at test_program.cpp",
                    "  <0,2> [pair]",
                    "visualize(pr) at test_program.cpp",
                    "  <1,2> [pair]",
                    # the "map" display hint names each value by its key
                    "visualize(pa) at test_program.cpp",
                    "  pairs=2 [pair_array]",
                    "    [3] = 4 [int]",
                    "    [5] = 6 [int]",
                    # no [More...] paging
                    "visualize(big) at test_program.cpp",
                    "  n=120 [int_array]",
                ]
                + [f"    [{i}] = {i} [int]" for i in range(120)]
                + [
                    # a call in another function, on a reference
                    "visualize(ref) at test_program.cpp",
                    "  <1,2> [const pair &]",
                    "",
                ]
            ),
        )
        self.assertEqual(errors, [])

    def test_bad_printers(self):
        output, errors = self.run_visualizer(gdb_printers="bad_printers.py")
        # exceptions in printers pass silently: the value stays empty and the
        # children are missing, for the expected output to catch
        self.assertIn("visualize(pr) at test_program.cpp\n   [pair]\n", output)
        self.assertIn(
            "visualize(arr) at test_program.cpp\n  n=3 [int_array]\nvisualize(pr)", output
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
        result = subprocess.run(
            [TOOLS["gdb"], "-nx", "-batch", "-ex", "python import gdb.dap"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            # gdb's error, as the import may also fail in a gdb 14 or later
            output = (result.stderr or result.stdout).strip()
            raise AssertionError(f"needs gdb 14 or later: {output}")

    def test_good_printers(self):
        output, errors = self.run_visualizer(gdb_printers="good_printers.py")
        self.assertEqual(
            output,
            "\n".join(
                [
                    "visualize(pr) at test_program.cpp",
                    "  <1,2> [pair]",
                    "visualize(arr) at test_program.cpp",
                    "  n=3 [int_array]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    "visualize(pr) at test_program.cpp",
                    "  <0,2> [pair]",
                    "visualize(pr) at test_program.cpp",
                    "  <1,2> [pair]",
                    # unlike OpenDebugAD7, gdb shows the "map" display hint's keys and values as children
                    "visualize(pa) at test_program.cpp",
                    "  pairs=2 [pair_array]",
                    "    key0 = 3 [int]",
                    "    value0 = 4 [int]",
                    "    key1 = 5 [int]",
                    "    value1 = 6 [int]",
                    "visualize(big) at test_program.cpp",
                    "  n=120 [int_array]",
                ]
                + [f"    [{i}] = {i} [int]" for i in range(120)]
                + [
                    # a call in another function, on a reference
                    "visualize(ref) at test_program.cpp",
                    "  <1,2> [const pair &]",
                    "",
                ]
            ),
        )
        self.assertEqual(errors, [])

    def test_bad_printers(self):
        # unlike through OpenDebugAD7, a printer that raises makes gdb fail the evaluation: the
        # run stops there, with gdb's message
        output, errors = self.run_visualizer(gdb_printers="bad_printers.py")
        self.assertEqual(output, "visualize(pr) at test_program.cpp\n")
        self.assertEqual(errors, ["There is no member named c."])

    def test_malformed_printers(self):
        # unlike through OpenDebugAD7, a script that doesn't load passes silently: values show
        # without printers, for the expected output to catch
        output, errors = self.run_visualizer(gdb_printers="malformed_printers.py")
        self.assertIn(
            "visualize(pr) at test_program.cpp\n   [pair]\n    a = 1 [int]\n    b = 2 [int]\n",
            output,
        )
        self.assertEqual(errors, [])

    def test_crash(self):
        output, errors = self.run_visualizer("-c", gdb_printers="good_printers.py")
        # the crash comes before any call, so nothing has printed
        self.assertEqual(output, "")
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("main", crash[0])

    # a program that exits with an error code fails the run
    def test_exit_code(self):
        output, errors = self.run_visualizer("-f", gdb_printers="good_printers.py")
        # it returns before any call, so nothing has printed
        self.assertEqual(output, "")
        self.assertEqual(errors, ["error: the program exited with code 1"])


# The lldb formatter tests whose outcome is the same through lldb-dap as through MIEngine, for the
# test classes of each.
class LldbFormatterTests:
    def test_good_formatters(self):
        output, errors = self.run_visualizer(lldb_formatters="good_formatters.py")
        self.assertEqual(
            re.sub(r"0x[0-9a-f]+", "0x?", output),
            "\n".join(
                [
                    # a summary does not hide the members
                    "visualize(pr) at test_program.cpp",
                    "  <1,2> [pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    "visualize(arr) at test_program.cpp",
                    "  n=3 [int_array]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    "visualize(pr) at test_program.cpp",
                    "  <0,2> [pair]",
                    "    a = 0 [int]",
                    "    b = 2 [int]",
                    "visualize(pr) at test_program.cpp",
                    "  <1,2> [pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    # synthetic children named by key, like the gdb "map" display hint in OpenDebugAD7
                    "visualize(pa) at test_program.cpp",
                    "  pairs=2 [pair_array]",
                    "    [3] = 4 [int]",
                    "    [5] = 6 [int]",
                    # no paging
                    "visualize(big) at test_program.cpp",
                    "  n=120 [int_array]",
                ]
                + [f"    [{i}] = {i} [int]" for i in range(120)]
                + [
                    # a call in another function, on a reference, whose address lldb shows before
                    # the summary
                    "visualize(ref) at test_program.cpp",
                    "  0x? <1,2> [const pair &]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    "",
                ]
            ),
        )
        self.assertEqual(errors, [])


# The lldb formatters through lldb's own DAP server (lldb-dap, or lldb-vscode before LLVM 18).
class LldbTests(LldbFormatterTests, FixtureTestCase):
    debugger = "lldb"
    debugger_tool = "lldb-dap"
    tools = ("lldb-dap",)

    def test_bad_formatters(self):
        # exceptions in formatters pass silently: a summary falls back to lldb's default and
        # synthetic children are missing, for the expected output to catch
        output, errors = self.run_visualizer(lldb_formatters="bad_formatters.py")
        self.assertRegex(
            output,
            r"visualize\(pr\) at test_program.cpp\n"
            r"  pair @ 0x[0-9a-f]+ \[pair\]\n    a = 1 \[int\]\n",
        )
        self.assertIn(
            "visualize(arr) at test_program.cpp\n  n=3 [int_array]\nvisualize(pr)", output
        )
        self.assertEqual(errors, [])

    def test_malformed_formatters(self):
        # importing the script fails, which lldb-dap only reports on its debug console: values
        # show without formatters, for the expected output to catch
        output, errors = self.run_visualizer(lldb_formatters="malformed_formatters.py")
        self.assertRegex(
            output,
            r"visualize\(arr\) at test_program.cpp\n"
            r"  int_array @ 0x[0-9a-f]+ \[int_array\]\n    data = ",
        )
        self.assertEqual(errors, [])

    def test_crash(self):
        output, errors = self.run_visualizer("-c", lldb_formatters="good_formatters.py")
        # the crash comes before any call, so nothing has printed
        self.assertEqual(output, "")
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("main", crash[0])


# natvis files and lldb formatters through MIEngine, with lldb (lldb-mi, LLDB's implementation of
# gdb's machine interface).
class MiengineLldbTests(MiengineNatvisTests, LldbFormatterTests, FixtureTestCase):
    debugger = "lldb"
    debugger_tool = "lldb-mi"
    tools = ("miengine", "lldb-mi")

    def test_bad_natvis(self):
        output, errors = self.run_visualizer(natvis="bad.natvis")
        # the DisplayString refers to a missing member: LLDB's error, over several lines, appears
        # in place of the value, for the expected output to catch
        self.assertIn("  <1,error: <user expression", output)
        self.assertIn("use of undeclared identifier 'no_such_member'", output)
        self.assertEqual(errors, [])
        # the ArrayItems <Size> is wrong, so the engine silently shows raw members
        self.assertIn("  {...} [int_array]\n    data = ", output)
        self.assertIn("\n    n = 3 [int]\n", output)

    def test_bad_formatters(self):
        # exceptions in formatters pass silently: a summary falls back to MIEngine's {...} and
        # synthetic children are missing, for the expected output to catch
        output, errors = self.run_visualizer(lldb_formatters="bad_formatters.py")
        self.assertIn(
            "visualize(pr) at test_program.cpp\n  {...} [pair]\n    a = 1 [int]\n", output
        )
        self.assertIn(
            "visualize(arr) at test_program.cpp\n  n=3 [int_array]\nvisualize(pr)", output
        )
        self.assertEqual(errors, [])

    def test_malformed_formatters(self):
        # importing the script fails, which passes silently: values show without formatters, for
        # the expected output to catch
        output, errors = self.run_visualizer(lldb_formatters="malformed_formatters.py")
        self.assertIn(
            "visualize(arr) at test_program.cpp\n  {...} [int_array]\n    data = ", output
        )
        self.assertEqual(errors, [])


# natvis through the dbgeng debug adapter (cxx_debug_visualize_dbgeng/), with the Windows debug
# engine, whose data model applies the natvis file.
class DbgengTests(FixtureTestCase):
    adapter = "dbgeng"
    debugger = "dbgeng"
    # without --dbgeng-dll, the adapter loads the Debugging Tools' dbgeng.dll
    debugger_tool = "dbgeng-dll"
    tools = ("dbgeng",)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.adapter_path = TOOLS["dbgeng"]

    def test_good_natvis(self):
        output, errors = self.run_visualizer(natvis="good.natvis")
        self.assertEqual(
            output,
            "\n".join(
                [
                    "visualize(pr) at test_program.cpp",
                    "  <1,2> [pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    "visualize(arr) at test_program.cpp",
                    "  {...} [int_array]",
                    "    [0] = 7 [int]",
                    "    [1] = 8 [int]",
                    "    [2] = 9 [int]",
                    "visualize(pr) at test_program.cpp",
                    "  <0,2> [pair]",
                    "    a = 0 [int]",
                    "    b = 2 [int]",
                    "visualize(pr) at test_program.cpp",
                    "  <1,2> [pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    "visualize(pa) at test_program.cpp",
                    "  {...} [pair_array]",
                    "    [0] = <3,4> [pair]",
                    "    [1] = <5,6> [pair]",
                    "visualize(big) at test_program.cpp",
                    "  {...} [int_array]",
                ]
                + [f"    [{i}] = {i} [int]" for i in range(120)]
                + [
                    # a call in another function, on a reference, which the adapter shows as the
                    # object it refers to
                    "visualize(ref) at test_program.cpp",
                    "  <1,2> [pair]",
                    "    a = 1 [int]",
                    "    b = 2 [int]",
                    "",
                ]
            ),
        )
        self.assertEqual(errors, [])

    def test_malformed_natvis(self):
        # the engine does not load the file, which the adapter reports as natvis diagnostics
        output, errors = self.run_visualizer(natvis="malformed.natvis")
        self.assertIn("{...} [pair]", output)
        self.assertTrue(any(e.startswith("[Natvis]") for e in errors), errors)

    def test_crash(self):
        output, errors = self.run_visualizer("-c", natvis="good.natvis")
        # the crash comes before any call, so nothing has printed
        self.assertEqual(output, "")
        crash = [e for e in errors if "program stopped unexpectedly" in e]
        self.assertEqual(len(crash), 1, errors)
        self.assertIn("main", crash[0])
