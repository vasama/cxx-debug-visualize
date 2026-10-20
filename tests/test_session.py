# Tests of the launch configuration, which need no debugger.

import os
import unittest

from cxx_debug_visualize.session import DebugSession


class LaunchConfigTests(unittest.TestCase):
    def test_natvis(self):
        cfg = DebugSession(
            "miengine", "OpenDebugAD7", "test_program", [], debugger="gdb", natvis="my.natvis"
        )._launch_config()
        self.assertEqual(cfg["visualizerFile"], os.path.abspath("my.natvis"))
        self.assertIs(cfg["showDisplayString"], True)
        self.assertNotIn("setupCommands", cfg)
        self.assertNotIn("miDebuggerArgs", cfg)

    def test_printers(self):
        cfg = DebugSession(
            "miengine",
            "OpenDebugAD7",
            "test_program",
            [],
            debugger="gdb",
            gdb_printers="my_printers.py",
        )._launch_config()
        self.assertNotIn("visualizerFile", cfg)
        # isolated: no gdb init files, no auto-loaded printers
        self.assertEqual(cfg["miDebuggerArgs"], "-nx")
        self.assertEqual(
            [c["text"] for c in cfg["setupCommands"]],
            [
                "-enable-pretty-printing",
                "set auto-load python-scripts off",
                f"source {os.path.abspath('my_printers.py')}",
            ],
        )

    def test_debugger_path(self):
        cfg = DebugSession(
            "miengine",
            "OpenDebugAD7",
            "test_program",
            [],
            debugger="gdb",
            debugger_path="/opt/gdb/bin/gdb",
            gdb_printers="my_printers.py",
        )._launch_config()
        self.assertEqual(cfg["miDebuggerPath"], "/opt/gdb/bin/gdb")
        # without a path, OpenDebugAD7 uses the gdb on PATH
        cfg = DebugSession(
            "miengine",
            "OpenDebugAD7",
            "test_program",
            [],
            debugger="gdb",
            gdb_printers="my_printers.py",
        )._launch_config()
        self.assertNotIn("miDebuggerPath", cfg)

    def test_lldb_formatters(self):
        cfg = DebugSession(
            None, None, "test_program", [], debugger="lldb", lldb_formatters="my_formatters.py"
        )._launch_config()
        self.assertEqual(cfg["program"], os.path.abspath("test_program"))
        # isolated: lldb's built-in C++ formatters are disabled before the script is loaded
        self.assertEqual(
            cfg["initCommands"],
            [
                "type category disable -l c++",
                f"command script import {os.path.abspath('my_formatters.py')}",
            ],
        )

    def test_exactly_one_visualizer(self):
        with self.assertRaises(AssertionError):
            DebugSession("miengine", "OpenDebugAD7", "test_program", [], debugger="gdb")
        with self.assertRaises(AssertionError):
            DebugSession(
                "miengine",
                "OpenDebugAD7",
                "test_program",
                [],
                debugger="gdb",
                natvis="my.natvis",
                gdb_printers="my_printers.py",
            )

    def test_dbgeng(self):
        cfg = DebugSession(
            "dbgeng",
            "dbgeng-adapter",
            "test_program",
            ["arg"],
            debugger="dbgeng",
            debugger_path="/debuggers/x64",
            natvis="my.natvis",
        )._launch_config()
        self.assertEqual(
            cfg,
            {
                "program": os.path.abspath("test_program"),
                "args": ["arg"],
                "cwd": os.path.dirname(os.path.abspath("test_program")),
                "visualizerFile": os.path.abspath("my.natvis"),
                "debuggerPath": "/debuggers/x64",
            },
        )

    # dbgeng is only supported through its debug adapter, and only with natvis
    def test_dbgeng_needs_adapter_and_natvis(self):
        with self.assertRaises(AssertionError):
            DebugSession(None, None, "test_program", [], debugger="dbgeng", natvis="my.natvis")
        with self.assertRaises(AssertionError):
            DebugSession(
                "dbgeng",
                "dbgeng-adapter",
                "test_program",
                [],
                debugger="dbgeng",
                gdb_printers="my.py",
            )

    # gdb's own DAP support (no adapter) knows nothing about natvis
    def test_native_dap_rejects_natvis(self):
        with self.assertRaises(AssertionError):
            DebugSession(None, None, "test_program", [], debugger="gdb", natvis="my.natvis")
        DebugSession(None, None, "test_program", [], debugger="gdb", gdb_printers="my_printers.py")
