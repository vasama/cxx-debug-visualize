# Tests of the command line, which need no debugger.

import contextlib
import io
import os
import unittest
from unittest import mock

from cxx_debug_visualize.cli import deduce_debugger_type, main


# Run cxx-debug-visualize with `args`, without the environment variables that name debug adapters;
# return (exit status, stderr lines).
def run_cli(*args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CXX_DEBUG_VISUALIZE_")}
    err = io.StringIO()
    with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stderr(err):
        try:
            status = main(list(args))
        except SystemExit as e:
            status = e.code
    return status, err.getvalue().splitlines()


class DebuggerTypeTests(unittest.TestCase):
    def test_from_file_name(self):
        for path, expected in [
            ("/usr/bin/gdb", "gdb"),
            ("/usr/bin/gdb-multiarch", "gdb"),
            ("/opt/cross/bin/x86_64-linux-gnu-gdb", "gdb"),
            ("/usr/lib/llvm-18/bin/lldb-dap", "lldb"),
            ("/usr/bin/lldb-vscode-16", "lldb"),
            ("C:/LLVM/bin/LLDB-DAP.EXE", "lldb"),
            ("/usr/bin/python3", None),
        ]:
            self.assertEqual(deduce_debugger_type(path), expected, path)

    # only the file name counts, not the directories
    def test_ignores_directories(self):
        self.assertIsNone(deduce_debugger_type("/opt/gdb/bin/debugger"))
        self.assertEqual(deduce_debugger_type("/home/lldb/bin/gdb"), "gdb")


# The options are checked before the files, so none of these need to exist.
class AdapterOptionTests(unittest.TestCase):
    # --trace prints the adapter and debugger chosen, before the missing files are reported
    def test_dbgeng_selects_adapter_and_debugger(self):
        status, errors = run_cli(
            "--dbgeng", "adapter.exe", "--natvis", "my.natvis", "--trace", "test.cpp", "test.exe"
        )
        self.assertEqual(status, 2)
        self.assertEqual(errors[:2], ["adapter: adapter.exe", "debugger: dbgeng"])

    def test_adapter_dbgeng_needs_path(self):
        status, errors = run_cli("--adapter", "dbgeng", "--natvis", "my.natvis", "t.cpp", "t.exe")
        self.assertEqual(status, 2)
        self.assertEqual(
            errors,
            [
                (
                    "error: dbgeng debug adapter not found; pass --dbgeng or set "
                    "CXX_DEBUG_VISUALIZE_DBGENG"
                )
            ],
        )

    def test_miengine_and_dbgeng_are_exclusive(self):
        status, errors = run_cli(
            "--miengine", "a", "--dbgeng", "b", "--natvis", "my.natvis", "t.cpp", "t.exe"
        )
        self.assertEqual(status, 2)
        self.assertIn("argument --dbgeng: not allowed with argument --miengine", errors[-1])

    def test_dbgeng_debugger_needs_dbgeng_adapter(self):
        status, errors = run_cli(
            "--debugger", "dbgeng", "--adapter", "miengine", "--natvis", "my.natvis", "t.cpp", "t"
        )
        self.assertEqual(status, 2)
        self.assertEqual(
            errors, ["error: --debugger dbgeng requires --adapter dbgeng, and vice versa"]
        )

    def test_dbgeng_needs_natvis(self):
        status, errors = run_cli("--dbgeng", "a", "--gdb-printers", "my.py", "t.cpp", "t.exe")
        self.assertEqual(status, 2)
        self.assertEqual(errors, ["error: --gdb-printers requires --debugger=gdb"])
