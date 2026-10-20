# Command line interface:
#
#     cxx-vistest --adapter OpenDebugAD7 --natvis my.natvis test.cpp ./prog \
#         | FileCheck test.cpp
#
#     cxx-vistest --adapter OpenDebugAD7 --gdb-printers my_printers.py test.cpp ./prog \
#         | FileCheck test.cpp

import argparse
import os
import sys

from .adapter import find_adapter
from .runner import Runner

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cxx-vistest",
                                     description="Unit tests for natvis files and gdb pretty "
                                                 "printers: visualizes the variable named at each "
                                                 "call to a function named `visualize`")

    parser.add_argument("--debugger", choices=("gdb", "lldb"), default="gdb",
                        help="debugger to use (default: gdb)")

    adapter = parser.add_mutually_exclusive_group()
    adapter.add_argument("--adapter", metavar="PATH",
                         default=os.environ.get("CXX_VISTEST_ADAPTER"),
                         help="path to the debug adapter, e.g. a build of MIEngine (default: "
                              "$CXX_VISTEST_ADAPTER)")

    adapter.add_argument("--vs-code-adapter", action="store_true",
                         help="use the debug adapter of the newest VS Code C/C++ extension "
                              "installed in ~/.vscode*/extensions")

    visualizer = parser.add_mutually_exclusive_group(required=True)
    visualizer.add_argument("--natvis", metavar="FILE", help="natvis file to test")
    visualizer.add_argument("--gdb-printers", metavar="FILE",
                            help="gdb pretty-printer script (Python) to test")
    visualizer.add_argument("--lldb-formatters", metavar="FILE",
                            help="lldb formatter script (Python) to test")

    parser.add_argument("source", help="C++ visualization test source")
    parser.add_argument("program", help="Unit test program (executed without arguments)")

    parser.add_argument("--trace", action="store_true", help="Print the DAP traffic to stderr")

    ns = parser.parse_args(argv)

    # Without a debug adapter, the debugger's native DAP support is used (GDB 14 and later, or
    # lldb-dap).
    use_adapter = ns.adapter is not None or ns.vs_code_adapter
    if ns.debugger == "lldb" and use_adapter:
        print("error: --debugger=lldb does not support a debug adapter", file=sys.stderr)
        return 2
    if ns.natvis and not use_adapter:
        print("error: --natvis requires a debug adapter; pass --adapter or --vs-code-adapter, or "
              "set CXX_VISTEST_ADAPTER", file=sys.stderr)
        return 2
    if ns.gdb_printers and ns.debugger != "gdb":
        print("error: --gdb-printers requires --debugger=gdb", file=sys.stderr)
        return 2
    if ns.lldb_formatters and ns.debugger != "lldb":
        print("error: --lldb-formatters requires --debugger=lldb", file=sys.stderr)
        return 2

    if ns.vs_code_adapter:
        ns.adapter = find_adapter()
        if ns.adapter is None:
            print("error: no VS Code C/C++ extension with an OpenDebugAD7 found", file=sys.stderr)
            return 2

    if ns.trace:
        native = "gdb -i dap" if ns.debugger == "gdb" else "lldb-dap"
        print(f"adapter: {ns.adapter or native}", file=sys.stderr)

    # Check that the specified debug adapter is executable:
    if ns.adapter is not None and not os.access(ns.adapter, os.X_OK):
        print("The specified debug adapter is not executable.", file=sys.stderr)
        return 2

    # Check that all specified paths refer to existing files:
    paths = [("program", ns.program), ("source file", ns.source)]
    if ns.adapter is not None:
        paths.append(("debug adapter", ns.adapter))
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

    runner = Runner(ns.adapter, ns.program, ns.source, debugger=ns.debugger, natvis=ns.natvis,
                    gdb_printers=ns.gdb_printers, lldb_formatters=ns.lldb_formatters,
                    log=(lambda m: print(m, file=sys.stderr)) if ns.trace else None)
    return 0 if runner.run() else 1

if __name__ == "__main__":
    sys.exit(main())
