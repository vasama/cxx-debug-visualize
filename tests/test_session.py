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
        # by default, gdb's own pretty printers show what natvis does not
        self.assertEqual([c["text"] for c in cfg["setupCommands"]], ["-enable-pretty-printing"])
        # no gdb init files
        self.assertEqual(cfg["miDebuggerArgs"], "-nx")

    def test_natvis_without_default_visualizers(self):
        cfg = DebugSession(
            "miengine",
            "OpenDebugAD7",
            "test_program",
            [],
            debugger="gdb",
            natvis="my.natvis",
            default_visualizers=False,
        )._launch_config()
        self.assertNotIn("setupCommands", cfg)

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
        # no gdb init files, but auto-loaded printers (e.g. libstdc++'s)
        self.assertEqual(cfg["miDebuggerArgs"], "-nx")
        self.assertEqual(
            [c["text"] for c in cfg["setupCommands"]],
            ["-enable-pretty-printing", f"source {os.path.abspath('my_printers.py')}"],
        )

    def test_printers_without_default_visualizers(self):
        cfg = DebugSession(
            "miengine",
            "OpenDebugAD7",
            "test_program",
            [],
            debugger="gdb",
            gdb_printers="my_printers.py",
            default_visualizers=False,
        )._launch_config()
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
        self.assertEqual(
            cfg["initCommands"], [f"command script import {os.path.abspath('my_formatters.py')}"]
        )

    def test_lldb_formatters_without_default_visualizers(self):
        cfg = DebugSession(
            None,
            None,
            "test_program",
            [],
            debugger="lldb",
            lldb_formatters="my_formatters.py",
            default_visualizers=False,
        )._launch_config()
        # isolated: lldb's built-in C++ formatters are disabled before the script is loaded
        self.assertEqual(
            cfg["initCommands"],
            [
                "type category disable -l c++",
                f"command script import {os.path.abspath('my_formatters.py')}",
            ],
        )

    # through MIEngine, lldb-mi reads no init files (it has no -nx), and LLDB's commands are setup
    # commands
    def test_miengine_lldb(self):
        cfg = DebugSession(
            "miengine",
            "OpenDebugAD7",
            "test_program",
            [],
            debugger="lldb",
            debugger_path="/usr/bin/lldb-mi",
            natvis="my.natvis",
        )._launch_config()
        self.assertEqual(cfg["MIMode"], "lldb")
        self.assertEqual(cfg["miDebuggerPath"], "/usr/bin/lldb-mi")
        self.assertEqual(cfg["visualizerFile"], os.path.abspath("my.natvis"))
        self.assertNotIn("miDebuggerArgs", cfg)
        self.assertNotIn("setupCommands", cfg)

    def test_miengine_lldb_formatters_without_default_visualizers(self):
        cfg = DebugSession(
            "miengine",
            "OpenDebugAD7",
            "test_program",
            [],
            debugger="lldb",
            lldb_formatters="my_formatters.py",
            default_visualizers=False,
        )._launch_config()
        self.assertEqual(
            [c["text"] for c in cfg["setupCommands"]],
            [
                "type category disable -l c++",
                f"command script import {os.path.abspath('my_formatters.py')}",
            ],
        )

    # without a visualizer under test, only the default visualizers are active
    def test_default_visualizers_only(self):
        cfg = DebugSession(
            "miengine", "OpenDebugAD7", "test_program", [], debugger="gdb"
        )._launch_config()
        self.assertNotIn("visualizerFile", cfg)
        self.assertEqual([c["text"] for c in cfg["setupCommands"]], ["-enable-pretty-printing"])
        cfg = DebugSession(None, None, "test_program", [], debugger="lldb")._launch_config()
        self.assertEqual(cfg["initCommands"], [])
        cfg = DebugSession(
            "dbgeng", "dbgeng-adapter", "test_program", [], debugger="dbgeng"
        )._launch_config()
        self.assertNotIn("visualizerFile", cfg)

    def test_at_most_one_visualizer(self):
        with self.assertRaises(AssertionError):
            DebugSession(
                "miengine",
                "OpenDebugAD7",
                "test_program",
                [],
                debugger="gdb",
                default_visualizers=False,
            )
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
                "defaultVisualizers": True,
                "debuggerPath": "/debuggers/x64",
            },
        )

    def test_dbgeng_without_default_visualizers(self):
        cfg = DebugSession(
            "dbgeng",
            "dbgeng-adapter",
            "test_program",
            [],
            debugger="dbgeng",
            natvis="my.natvis",
            default_visualizers=False,
        )._launch_config()
        self.assertIs(cfg["defaultVisualizers"], False)

    # dbgeng is only supported through its debug adapter, and only with natvis (or no visualizer)
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


# Which output the adapter's events report as problems; the events are given to the session as they
# would arrive.
class DiagnosticsTests(unittest.TestCase):
    @staticmethod
    def receive(session, category, text):
        session._handle_event({"event": "output", "body": {"category": category, "output": text}})

    def test_miengine_errors_and_natvis_diagnostics(self):
        session = DebugSession(
            "miengine", "OpenDebugAD7", "test_program", [], debugger="lldb", natvis="my.natvis"
        )
        error = "ERROR: Unable to start debugging. unable to locate lldb-server-18.1.3\n"
        natvis = "[Natvis] [Error] Error while reading file: my.natvis\n"
        self.receive(session, "stderr", error)
        # the program's own output, on stderr and stdout
        self.receive(session, "stderr", "something the program printed\n")
        self.receive(session, "stdout", "ERROR: printed by the program\n")
        self.receive(session, "console", natvis)
        self.assertEqual(session.diagnostics(), [error, natvis])

    # the prefix is MIEngine's: through lldb-dap, such stderr output is the program's
    def test_program_stderr_through_lldb_dap(self):
        session = DebugSession(
            None, None, "test_program", [], debugger="lldb", lldb_formatters="my_formatters.py"
        )
        self.receive(session, "stderr", "ERROR: printed by the program\n")
        self.assertEqual(session.diagnostics(), [])


# The exit code of the adapter's exited event, in whatever order the events arrive.
class ExitCodeTests(unittest.TestCase):
    def setUp(self):
        self.session = DebugSession(
            None, None, "test_program", [], debugger="gdb", gdb_printers="my_printers.py"
        )

    def test_exited_after_terminated(self):
        self.assertEqual(self.session.exit_code(), 0)
        self.session._handle_event({"event": "terminated", "body": {}})
        self.session._handle_event({"event": "exited", "body": {"exitCode": 3}})
        self.assertEqual(self.session.exit_code(), 3)

    # an exited event without a code, as a non-conforming adapter may send, is ignored
    def test_exited_without_code(self):
        for event in [{"event": "exited"}, {"event": "exited", "body": None}]:
            self.session._handle_event(event)
        self.assertEqual(self.session.exit_code(), 0)
