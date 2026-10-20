# Command line interface:
#
#     cxx-debug-visualize test.cpp ./test_program --gdb-printers my_printers.py
#
#     cxx-debug-visualize test.cpp ./test_program --debugger lldb --lldb-formatters my_formatters.py
#
#     cxx-debug-visualize test.cpp ./test_program --miengine OpenDebugAD7 --natvis my.natvis
#
#     cxx-debug-visualize test.cpp ./test_program.exe --dbgeng dbgeng-adapter.exe --natvis my.natvis

import argparse
import os
import sys

from .adapter import find_miengine
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

    parser.add_argument(
        "--debugger",
        choices=("gdb", "lldb", "dbgeng"),
        help="debugger to use; dbgeng is the Windows debug engine, only through the dbgeng adapter",
    )
    parser.add_argument(
        "--debugger-path",
        metavar="PATH",
        help="the gdb executable, the lldb DAP server (lldb-dap or lldb-vscode) or through MIEngine "
        "lldb-mi, or for dbgeng the directory of dbgeng.dll or a file in it (default: gdb, "
        "lldb-dap, lldb-vscode or lldb-mi available on PATH; for dbgeng, the Debugging Tools for "
        "Windows)",
    )

    parser.add_argument(
        "--adapter",
        choices=("native", "miengine", "dbgeng"),
        help="the debugger's native DAP support, the MIEngine debug adapter (OpenDebugAD7), or the "
        "dbgeng debug adapter (default: dbgeng with --debugger dbgeng or --dbgeng, otherwise "
        "miengine with --natvis or --miengine, otherwise native)",
    )
    adapters = parser.add_mutually_exclusive_group()
    adapters.add_argument(
        "--miengine",
        metavar="PATH",
        help="MIEngine debug adapter (OpenDebugAD7) path (e.g. a build of MIEngine) (default: "
        "$CXX_DEBUG_VISUALIZE_MIENGINE, otherwise the user's home directory is searched for an "
        "installed VS Code C/C++ extension)",
    )
    adapters.add_argument(
        "--dbgeng",
        metavar="PATH",
        help="dbgeng debug adapter path (default: $CXX_DEBUG_VISUALIZE_DBGENG)",
    )

    # Without a visualizer under test, only the default visualizers are active.
    visualizer = parser.add_mutually_exclusive_group()
    visualizer.add_argument("--natvis", metavar="FILE", help="natvis file")
    visualizer.add_argument(
        "--gdb-printers", metavar="FILE", help="gdb pretty-printer script (Python)"
    )
    visualizer.add_argument(
        "--lldb-formatters", metavar="FILE", help="lldb formatter script (Python)"
    )
    parser.add_argument(
        "--no-default-visualizers",
        action="store_true",
        help="disable default visualizers loaded by the debugger (e.g. libstdc++'s pretty "
        "printers, lldb's C++ formatters, or MSSTL Natvis files)",
    )

    parser.add_argument("source", help="test program source")
    parser.add_argument("program", help="test program executable")
    parser.add_argument(
        "program_args",
        nargs="*",
        metavar="ARG",
        help="arguments passed to the test program; use -- to escape options",
    )

    parser.add_argument(
        "--print-line-numbers",
        action="store_true",
        help="Print line numbers for each visualization",
    )

    parser.add_argument("--trace", action="store_true", help="Print the DAP traffic to stderr")

    ns = parser.parse_intermixed_args(argv)

    if ns.no_default_visualizers and not (ns.natvis or ns.gdb_printers or ns.lldb_formatters):
        print(
            "error: --no-default-visualizers requires --natvis, --gdb-printers or "
            "--lldb-formatters",
            file=sys.stderr,
        )
        return 2

    # Without --debugger, the debugger type is dbgeng with the dbgeng adapter (--adapter dbgeng or
    # --dbgeng), and is otherwise deduced from the visualizer: gdb for --gdb-printers, lldb for
    # --lldb-formatters. natvis files work with either, so with --natvis, or without a visualizer,
    # it is deduced from --debugger-path, and is otherwise dbgeng on Windows and gdb elsewhere.
    debugger_path = ns.debugger_path and os.path.abspath(ns.debugger_path)

    if ns.debugger is None:
        if debugger_path:
            ns.debugger = deduce_debugger_type(debugger_path)

        if ns.debugger is None:
            if ns.adapter == "dbgeng" or ns.dbgeng:
                ns.debugger = "dbgeng"
            elif ns.gdb_printers:
                ns.debugger = "gdb"
            elif ns.lldb_formatters:
                ns.debugger = "lldb"
            else:
                ns.debugger = "dbgeng" if os.name == "nt" else "gdb"

        if ns.debugger is None:
            print("error: cannot deduce debugger type; use --debugger to specify", file=sys.stderr)
            return 2

    # If --adapter was not specified explicitly, deduce it as:
    #   * "dbgeng"    if debugger is "dbgeng"
    #   * "miengine"  if --miengine was specified, or
    #                 if --natvis was specified (with debugger "gdb" or "lldb")
    #
    #   * "native"    otherwise
    if ns.adapter is None:
        if ns.debugger == "dbgeng":
            ns.adapter = "dbgeng"
        elif ns.miengine or ns.natvis:
            ns.adapter = "miengine"
        else:
            ns.adapter = "native"

    if (ns.debugger == "dbgeng") != (ns.adapter == "dbgeng"):
        print("error: --debugger dbgeng requires --adapter dbgeng, and vice versa", file=sys.stderr)
        return 2

    if ns.miengine is not None and ns.adapter != "miengine":
        print("error: --miengine requires --adapter=miengine", file=sys.stderr)
        return 2
    if ns.dbgeng is not None and ns.adapter != "dbgeng":
        print("error: --dbgeng requires --adapter=dbgeng", file=sys.stderr)
        return 2
    if ns.natvis and ns.adapter == "native":
        print("error: --natvis requires --adapter=miengine or --adapter=dbgeng", file=sys.stderr)
        return 2
    if ns.gdb_printers and ns.debugger != "gdb":
        print("error: --gdb-printers requires --debugger=gdb", file=sys.stderr)
        return 2
    if ns.lldb_formatters and ns.debugger != "lldb":
        print("error: --lldb-formatters requires --debugger=lldb", file=sys.stderr)
        return 2

    # The debug adapter executable (if any):
    # * MIEngine:  --miengine, $CXX_DEBUG_VISUALIZE_MIENGINE, or OpenDebugAD7 found in a VS Code
    #              C/C++ extension installed in the user home directory.
    # * dbgeng:    --dbgeng or $CXX_DEBUG_VISUALIZE_DBGENG.
    # * native:    none
    adapter_path = None
    if ns.adapter == "miengine":
        adapter_path = (
            ns.miengine or os.environ.get("CXX_DEBUG_VISUALIZE_MIENGINE") or find_miengine()
        )
        if adapter_path is None:
            print(
                "error: MIEngine debug adapter not found; pass --miengine, set "
                "CXX_DEBUG_VISUALIZE_MIENGINE, or install VS Code's C/C++ extension",
                file=sys.stderr,
            )
            return 2
    elif ns.adapter == "dbgeng":
        adapter_path = ns.dbgeng or os.environ.get("CXX_DEBUG_VISUALIZE_DBGENG")
        if adapter_path is None:
            print(
                "error: dbgeng debug adapter not found; pass --dbgeng or set "
                "CXX_DEBUG_VISUALIZE_DBGENG",
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
        None if ns.adapter == "native" else ns.adapter,
        adapter_path,
        ns.source,
        ns.program,
        ns.program_args,
        debugger=ns.debugger,
        debugger_path=debugger_path,
        natvis=ns.natvis,
        gdb_printers=ns.gdb_printers,
        lldb_formatters=ns.lldb_formatters,
        default_visualizers=not ns.no_default_visualizers,
        print_line_numbers=ns.print_line_numbers,
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
