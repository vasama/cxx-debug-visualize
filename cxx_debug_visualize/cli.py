# Command line interface:
#
#     cxx-debug-visualize test.cpp ./test_program --gdb-printers my_printers.py
#
#     cxx-debug-visualize test.cpp ./test_program --debugger lldb --lldb-formatters my_formatters.py
#
#     cxx-debug-visualize test.cpp ./test_program --adapter OpenDebugAD7 --natvis my.natvis

import argparse
import os
import sys

from .adapter import find_adapter
from .runner import Runner


# Deduces the type of debugger ("gdb" or "lldb"), from the executable path (e.g. gdb-multiarch,
# lldb-dap, lldb-vscode-16), or None if deduction fails.
def deduce_debugger_type(path: str) -> str | None:
    name = os.path.basename(path).lower()
    if "lldb" in name:
        return "lldb"
    if "gdb" in name:
        return "gdb"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cxx-debug-visualize",
        description="Unit tests for natvis files and gdb pretty "
        "printers: visualizes the variable named at each "
        "call to a function named `visualize`",
    )

    parser.add_argument("--debugger", choices=("gdb", "lldb"), help="debugger to use")
    parser.add_argument(
        "--debugger-path",
        metavar="PATH",
        help="the gdb executable, or lldb DAP server (lldb-dap or lldb-vscode) (default: gdb, "
        ", lldb-dap, or lldb-vscode available on PATH)",
    )

    parser.add_argument(
        "--adapter",
        choices=("native", "vs"),
        help="the debugger's native DAP support, or the Visual Studio debug adapter (OpenDebugAD7) "
        "(default: vs if either --natvis or --vs-adapter is specified, otherwise native)",
    )
    parser.add_argument(
        "--vs-adapter",
        metavar="PATH",
        help="Visual Studio debug adapter path (e.g. a build of MIEngine) (default: "
        "$CXX_DEBUG_VISUALIZE_VS_ADAPTER, otherwise the user's home directory is searched for an "
        "installed VS Code C/C++ extension)",
    )

    visualizer = parser.add_mutually_exclusive_group(required=True)
    visualizer.add_argument("--natvis", metavar="FILE", help="natvis file")
    visualizer.add_argument(
        "--gdb-printers", metavar="FILE", help="gdb pretty-printer script (Python)"
    )
    visualizer.add_argument(
        "--lldb-formatters", metavar="FILE", help="lldb formatter script (Python)"
    )

    parser.add_argument("source", help="test program source")
    parser.add_argument("program", help="test program executable")
    parser.add_argument(
        "program_args",
        nargs="*",
        metavar="ARG",
        help="arguments passed to the test program; use -- to escape options",
    )

    parser.add_argument("--trace", action="store_true", help="Print the DAP traffic to stderr")

    ns = parser.parse_args(argv)

    # Without --debugger, the debugger type is deduced from the visualizer: gdb for --gdb-printers,
    # lldb for --lldb-formatters. natvis files work with either, so with --natvis it is deduced from
    # --debugger-path, and is otherwise gdb.
    debugger_path = ns.debugger_path and os.path.abspath(ns.debugger_path)
    if ns.debugger is None:
        if ns.gdb_printers:
            ns.debugger = "gdb"
        elif ns.lldb_formatters:
            ns.debugger = "lldb"
        elif debugger_path:
            ns.debugger = deduce_debugger_type(debugger_path)

        if ns.debugger is None:
            print(
                "error: cannot deduce debugger type from its path; use --debugger to specify",
                file=sys.stderr,
            )
            return 2

    # If --adapter was not specified explicitly, deduce it as "vs" if --natvis or --vs-adapter were
    # specified, and as "native" otherwise.
    if ns.adapter is None:
        if ns.natvis or ns.vs_adapter:
            ns.adapter = "vs"
        else:
            ns.adapter = "native"

    if ns.adapter == "vs" and ns.debugger == "lldb":
        print(
            "error: using lldb via the Visual Studio debug adapter is not currently supported",
            file=sys.stderr,
        )
        return 2
    if ns.adapter == "native" and ns.vs_adapter is not None:
        print("error: --vs-adapter requires --adapter vs", file=sys.stderr)
        return 2
    if ns.natvis and ns.adapter != "vs":
        print("error: --natvis requires --adapter vs", file=sys.stderr)
        return 2
    if ns.gdb_printers and ns.debugger != "gdb":
        print("error: --gdb-printers requires --debugger=gdb", file=sys.stderr)
        return 2
    if ns.lldb_formatters and ns.debugger != "lldb":
        print("error: --lldb-formatters requires --debugger=lldb", file=sys.stderr)
        return 2

    # The Visual Studio debug adapter: --vs-adapter, $CXX_DEBUG_VISUALIZE_VS_ADAPTER, or a debug
    # adapter found in an installed VS Code C/C++ extension. None for native DAP support.
    adapter_path = None
    if ns.adapter == "vs":
        adapter_path = (
            ns.vs_adapter or os.environ.get("CXX_DEBUG_VISUALIZE_VS_ADAPTER") or find_adapter()
        )
        if adapter_path is None:
            print(
                "error: Visual Studio debug adapter not found; pass --vs-adapter, set "
                "CXX_DEBUG_VISUALIZE_VS_ADAPTER, or install VS Code's C/C++ extension",
                file=sys.stderr,
            )
            return 2

    if ns.trace:
        native = "gdb -i dap" if ns.debugger == "gdb" else "lldb-dap"
        print(f"adapter: {adapter_path or native}", file=sys.stderr)
        print(f"debugger: {debugger_path or ns.debugger}", file=sys.stderr)

    # Check that all specified paths refer to existing files:
    paths = [("program", ns.program), ("source file", ns.source)]
    if adapter_path is not None:
        paths.append(("debug adapter", adapter_path))
    if debugger_path is not None:
        paths.append(("debugger", debugger_path))
    if ns.natvis:
        paths.append(("natvis file", ns.natvis))
    if ns.gdb_printers:
        paths.append(("pretty-printer script", ns.gdb_printers))
    if ns.lldb_formatters:
        paths.append(("lldb formatter script", ns.lldb_formatters))
    missing = [(what, path) for what, path in paths if not os.path.isfile(path)]
    for what, path in missing:
        print(f"error: {what} not found: {path}", file=sys.stderr)
    if missing:
        return 2

    # Check that the specified debug adapter and debugger are executable:
    if adapter_path is not None and not os.access(adapter_path, os.X_OK):
        print("error: the specified debug adapter is not executable", file=sys.stderr)
        return 2
    if debugger_path is not None and not os.access(debugger_path, os.X_OK):
        print("error: the specified debugger is not executable", file=sys.stderr)
        return 2

    runner = Runner(
        adapter_path,
        ns.source,
        ns.program,
        ns.program_args,
        debugger=ns.debugger,
        debugger_path=debugger_path,
        natvis=ns.natvis,
        gdb_printers=ns.gdb_printers,
        lldb_formatters=ns.lldb_formatters,
        log=(lambda m: print(m, file=sys.stderr)) if ns.trace else None,
    )

    try:
        if runner.run():
            return 0
    except OSError as e:
        if not (isinstance(e, BrokenPipeError) or getattr(e, "winerror", None) == 232):
            raise

        # Avoid subsequent errors on exit if the stdout reader side was closed early:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())

    return 1
