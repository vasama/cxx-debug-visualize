# Finding and starting the OpenDebugAD7 debug adapter (MIEngine).
#
# This is the adapter behind the "cppdbg" debug type of the VS Code C/C++
# extension (ms-vscode.cpptools); it is where natvis support is implemented.

import glob
import os
import re
import sys

# Where VS Code, and its server for remote development, keep extensions,
# relative to the home directory.
_EXTENSION_DIRS = (".vscode", ".vscode-server", ".vscode-insiders", ".vscode-server-insiders")
_EXECUTABLE = "OpenDebugAD7.exe" if sys.platform == "win32" else "OpenDebugAD7"


# The OpenDebugAD7 of the newest VS Code C/C++ extension installed in the
# user's home directory, or None if there is none.
#
# The .vsix does not preserve permissions; the extension makes its binaries
# executable when it is first activated, so versions VS Code has not yet
# activated (e.g. right after an update) are skipped.
def find_adapter():
    candidates = []
    for directory in _EXTENSION_DIRS:
        extensions = os.path.join(os.path.expanduser("~"), directory, "extensions")
        candidates += glob.glob(os.path.join(extensions, "ms-vscode.cpptools-[0-9]*",
                                             "debugAdapters", "bin", _EXECUTABLE))
    candidates = [path for path in candidates if os.access(path, os.X_OK)]
    return max(candidates, key=_extension_version, default=None)


# (major, minor, patch) of the extension an adapter path belongs to.
def _extension_version(path):
    m = re.search(r"/ms-vscode\.cpptools-(\d+)\.(\d+)\.(\d+)-", path)
    return tuple(int(n) for n in m.groups()) if m else (0, 0, 0)


# Command line used to start the adapter.
#
# The extension ships a self-contained executable; a framework-dependent build
# of MIEngine produces OpenDebugAD7.dll, which runs via `dotnet`.
def adapter_argv(path):
    if path.endswith(".dll"):
        return ["dotnet", path]

    return [path]
