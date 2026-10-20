# Tests of finding OpenDebugAD7 in installed VS Code extensions.

import os
import shutil
import tempfile
import unittest
from unittest import mock

from cxx_debug_visualize.adapter import _EXECUTABLE, find_adapter


class FindAdapterTests(unittest.TestCase):
    # find_adapter() searches the home directory, i.e. $HOME
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="cxx-debug-visualize-home-")
        home = mock.patch.dict(os.environ, {"HOME": self.home})
        home.start()
        self.addCleanup(home.stop)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    # Install a fake extension; return its adapter's path.
    def install(self, extensions_dir, extension, with_adapter=True, executable=True):
        bin_dir = os.path.join(self.home, extensions_dir, "extensions", extension,
                               "debugAdapters", "bin")
        os.makedirs(bin_dir)
        path = os.path.join(bin_dir, _EXECUTABLE)
        if with_adapter:
            open(path, "w").close()
            os.chmod(path, 0o755 if executable else 0o644)
        return path

    def test_none_installed(self):
        self.assertIsNone(find_adapter())

    def test_newest_version_wins(self):
        self.install(".vscode", "ms-vscode.cpptools-1.9.0-linux-x64")
        newest = self.install(".vscode-server", "ms-vscode.cpptools-1.34.10-linux-x64")
        self.install(".vscode", "ms-vscode.cpptools-1.34.4-linux-x64")
        self.assertEqual(find_adapter(), newest)

    def test_ignores_other_extensions_and_incomplete_installs(self):
        self.install(".vscode", "ms-vscode.cpptools-extension-pack-1.3.0")
        self.install(".vscode", "ms-vscode.cpptools-2.0.0-linux-x64", with_adapter=False)
        self.assertIsNone(find_adapter())
        wanted = self.install(".vscode-insiders", "ms-vscode.cpptools-1.20.0-linux-x64")
        self.assertEqual(find_adapter(), wanted)

    # a version VS Code has not activated yet, e.g. right after an update
    @unittest.skipIf(os.name == "nt", "no execute permission on Windows")
    def test_skips_non_executable(self):
        wanted = self.install(".vscode", "ms-vscode.cpptools-1.20.0-linux-x64")
        self.install(".vscode", "ms-vscode.cpptools-1.21.0-linux-x64", executable=False)
        self.assertEqual(find_adapter(), wanted)


if __name__ == "__main__":
    unittest.main()
