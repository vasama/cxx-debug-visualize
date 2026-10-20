# Command line interface:
#
#     test_visualizers --adapter OpenDebugAD7 --natvis my.natvis test.cpp ./prog \
#         | FileCheck test.cpp
#
#     test_visualizers --adapter OpenDebugAD7 --printers my_printers.py test.cpp ./prog \
#         | FileCheck test.cpp

import argparse
import os
import sys

from .adapter import find_adapter
from .runner import Runner

def main(argv=None):
    parser = argparse.ArgumentParser(prog="test_visualizers",
                                     description="Unit tests for natvis files and gdb pretty "
                                                 "printers: visualizes the variable named at each"
                                                 "call to a function named `check_visualizers`")

    parser.add_argument("--adapter", metavar="PATH",
                        default=os.environ.get("TEST_VISUALIZERS_ADAPTER"),
                        help="path to the debug adapter, e.gs. a build of MIEngine (default: "
                             "$TEST_VISUALIZERS_ADAPTER if set, otherwise the newest VS Code "
                             "C/C++ extension installed in ~/.vscode*/extensions)")

    visualizer = parser.add_mutually_exclusive_group(required=True)
    visualizer.add_argument("--natvis", metavar="FILE", help="natvis file to test")
    visualizer.add_argument("--printers", metavar="FILE",
                            help="gdb pretty-printer script (Python) to test")

    parser.add_argument("source", help="C++ visualization test source")
    parser.add_argument("program", help="Unit test program (executed without arguments)")

    parser.add_argument("--trace", action="store_true", help="Print the DAP traffic to stderr")

    ns = parser.parse_args(argv)

    # Find debug adapter if it was not specified by the user:
    if ns.adapter is None:
        ns.adapter = find_adapter()
        if ns.adapter is None:
            print("error: no OpenDebugAD7 found; set TEST_VISUALIZERS_ADAPTER, or pass --adapter",
                  file=sys.stderr)
            return 2

    if ns.trace:
        print(f"adapter: {ns.adapter}", file=sys.stderr)

    # Check that the specified debug adapter is executable:
    if not os.access(ns.adapter, os.X_OK):
        print("The specified debug adapter is not executable.", file=sys.stderr)
        return 2

    # Check that all specified paths refer to existing files:
    paths = [("debug adapter", ns.adapter), ("program", ns.program), ("source file", ns.source)]
    if ns.natvis:
        paths.append(("natvis file", ns.natvis))
    else:
        paths.append(("pretty-printer script", ns.printers))
    missing = [(what, path) for what, path in paths if not os.path.isfile(path)]
    for what, path in missing:
        print(f"error: {what} not found: {path}", file=sys.stderr)
    if missing:
        return 2

    runner = Runner(ns.adapter, ns.program, ns.source, natvis=ns.natvis, printers=ns.printers,
                    log=(lambda m: print(m, file=sys.stderr)) if ns.trace else None)
    return 0 if runner.run() else 1

if __name__ == "__main__":
    sys.exit(main())
