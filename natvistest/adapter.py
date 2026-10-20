"""Starting the OpenDebugAD7 debug adapter (MIEngine).

This is the adapter behind the "cppdbg" debug type of the VS Code C/C++
extension (ms-vscode.cpptools); it is where natvis support is implemented.
Its path is always given explicitly (`--adapter`); nothing is searched for.
"""

import os


def adapter_argv(path):
    """Command line used to start the adapter.

    The extension ships a self-contained executable; a framework-dependent
    build of MIEngine produces OpenDebugAD7.dll, which runs via `dotnet`.
    """
    if path.endswith(".dll"):
        return ["dotnet", path]
    if not os.access(path, os.X_OK):
        # the .vsix is a zip file, which does not preserve permissions
        try:
            os.chmod(path, os.stat(path).st_mode | 0o755)
        except OSError:
            pass
    return [path]
