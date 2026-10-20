# Tests of the launch configuration, which need no debugger.

import os
import unittest

from cxx_vistest.session import DebugSession


class LaunchConfigTests(unittest.TestCase):
    def test_natvis(self):
        cfg = DebugSession("adapter", "prog", debugger="gdb", natvis="my.natvis")._launch_config()
        self.assertEqual(cfg["visualizerFile"], os.path.abspath("my.natvis"))
        self.assertIs(cfg["showDisplayString"], True)
        self.assertNotIn("setupCommands", cfg)
        self.assertNotIn("miDebuggerArgs", cfg)

    def test_printers(self):
        cfg = DebugSession("adapter", "prog", debugger="gdb",
                           gdb_printers="my_printers.py")._launch_config()
        self.assertNotIn("visualizerFile", cfg)
        # isolated: no gdb init files, no auto-loaded printers
        self.assertEqual(cfg["miDebuggerArgs"], "-nx")
        self.assertEqual([c["text"] for c in cfg["setupCommands"]], [
            "-enable-pretty-printing",
            "set auto-load python-scripts off",
            f"source {os.path.abspath('my_printers.py')}",
        ])

    def test_lldb_formatters(self):
        cfg = DebugSession(None, "prog", debugger="lldb",
                           lldb_formatters="my_formatters.py")._launch_config()
        self.assertEqual(cfg["program"], os.path.abspath("prog"))
        # isolated: lldb's built-in C++ formatters are disabled before the script is loaded
        self.assertEqual(cfg["initCommands"], [
            "type category disable -l c++",
            f"command script import {os.path.abspath('my_formatters.py')}",
        ])

    def test_exactly_one_visualizer(self):
        with self.assertRaises(AssertionError):
            DebugSession("adapter", "prog", debugger="gdb")
        with self.assertRaises(AssertionError):
            DebugSession("adapter", "prog", debugger="gdb", natvis="my.natvis",
                         gdb_printers="my_printers.py")

    # gdb's own DAP support (no adapter) knows nothing about natvis
    def test_native_dap_rejects_natvis(self):
        with self.assertRaises(AssertionError):
            DebugSession(None, "prog", debugger="gdb", natvis="my.natvis")
        DebugSession(None, "prog", debugger="gdb", gdb_printers="my_printers.py")


if __name__ == "__main__":
    unittest.main()
