# Tests of the command line helpers, which need no debugger.

import unittest

from cxx_debug_visualize.cli import deduce_debugger_type

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
