# Tests of the launch configuration, which need no debugger.

import os
import unittest

from test_visualizers.session import DebugSession


class LaunchConfigTests(unittest.TestCase):
    def test_natvis(self):
        cfg = DebugSession("adapter", "prog", natvis="my.natvis")._launch_config()
        self.assertEqual(cfg["visualizerFile"], os.path.abspath("my.natvis"))
        self.assertIs(cfg["showDisplayString"], True)
        self.assertNotIn("setupCommands", cfg)
        self.assertNotIn("miDebuggerArgs", cfg)

    def test_printers(self):
        cfg = DebugSession("adapter", "prog", printers="my_printers.py")._launch_config()
        self.assertNotIn("visualizerFile", cfg)
        # isolated: no gdb init files, no auto-loaded printers
        self.assertEqual(cfg["miDebuggerArgs"], "-nx")
        self.assertEqual([c["text"] for c in cfg["setupCommands"]], [
            "-enable-pretty-printing",
            "set auto-load python-scripts off",
            f"source {os.path.abspath('my_printers.py')}",
        ])

    def test_exactly_one_visualizer(self):
        with self.assertRaises(ValueError):
            DebugSession("adapter", "prog")
        with self.assertRaises(ValueError):
            DebugSession("adapter", "prog", natvis="my.natvis", printers="my_printers.py")

    # gdb's own DAP support (no adapter) knows nothing about natvis
    def test_native_dap_rejects_natvis(self):
        with self.assertRaises(ValueError):
            DebugSession(None, "prog", natvis="my.natvis")
        DebugSession(None, "prog", printers="my_printers.py")


if __name__ == "__main__":
    unittest.main()
