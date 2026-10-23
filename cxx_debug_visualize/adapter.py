# Finding and starting the OpenDebugAD7 debug adapter (MIEngine).
#
# This is the adapter behind the "cppdbg" debug type of the VS Code C/C++
# extension (ms-vscode.cpptools); it is where natvis support is implemented.

import os
import re
import shutil
import sys

_OPENDEBUGAD7_EXE = "OpenDebugAD7.exe" if sys.platform == "win32" else "OpenDebugAD7"
_VS_CODE_DIRECTORIES = (".vscode", ".vscode-server", ".vscode-insiders", ".vscode-server-insiders")
_VS_CODE_CCXX_EXTENSION_RE = re.compile(r"ms-vscode\.cpptools-(\d+)\.(\d+)\.(\d+)(?:-.+)?")


# The OpenDebugAD7 of the newest VS Code C/C++ extension installed in the user's home directory, or
# None if not found.
#
# The .vsix does not preserve permissions. The extension makes its binaries executable when it is
# first activated, so versions VS Code has not yet activated (e.g. after an update) are skipped.
def find_miengine() -> str | None:
    # (version, path) of each adapter found
    candidates: list[tuple[tuple[int, ...], str]] = []

    for directory in _VS_CODE_DIRECTORIES:
        extensions = os.path.join(os.path.expanduser("~"), directory, "extensions")
        try:
            entries = os.listdir(extensions)
        except OSError:
            continue
        for entry_name in entries:
            match = _VS_CODE_CCXX_EXTENSION_RE.fullmatch(entry_name)
            path = os.path.join(extensions, entry_name, "debugAdapters", "bin", _OPENDEBUGAD7_EXE)
            if match and os.access(path, os.X_OK):
                candidates.append((tuple(int(n) for n in match.groups()), path))

    return max(candidates)[1] if candidates else None


# lldb's own DAP server on PATH, or None if not found. LLVM 18 renamed it from lldb-vscode to
# lldb-dap.
def find_lldb_dap() -> str | None:
    return shutil.which("lldb-dap") or shutil.which("lldb-vscode")


# Command line used to start OpenDebugAD7.
#
# The VS Code C/C++ extension ships a self-contained executable. A .NET framework-dependent build of
# MIEngine produces OpenDebugAD7.dll, which runs via `dotnet`.
def miengine_argv(path: str) -> list[str]:
    if path.endswith(".dll"):
        return ["dotnet", path]

    return [path]
