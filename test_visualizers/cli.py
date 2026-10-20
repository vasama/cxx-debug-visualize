# Command line interface.
#
#     test_visualizers run --adapter OpenDebugAD7 --natvis my.natvis test.cpp ./prog \
#         | FileCheck test.cpp
#     test_visualizers run --adapter OpenDebugAD7 --printers my_printers.py test.cpp ./prog \
#         | FileCheck test.cpp

import argparse
import os
import sys

from .runner import Runner


def main(argv=None):
    parser = argparse.ArgumentParser(prog="test_visualizers",
                                     description="Unit tests for natvis files and gdb pretty "
                                     "printers, run through the same debug adapter VS Code "
                                     "uses (OpenDebugAD7/MIEngine).")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="print the Variables tree at every check_visualizer() "
                         "call, for FileCheck")
    run.add_argument("--adapter", required=True, metavar="PATH",
                     help="path to OpenDebugAD7 (e.g. <cpptools extension>/debugAdapters/bin/"
                     "OpenDebugAD7, or a build of MIEngine)")
    visualizer = run.add_mutually_exclusive_group(required=True)
    visualizer.add_argument("--natvis", metavar="FILE", help="natvis file to test")
    visualizer.add_argument("--printers", metavar="FILE",
                            help="gdb pretty-printer script (Python) to test")
    run.add_argument("--trace", action="store_true", help="print the DAP traffic to stderr")
    run.add_argument("source", help="C++ test source whose 'check_visualizer(identifier);' "
                     "lines get breakpoints")
    run.add_argument("program", help="test program (run without arguments)")

    ns = parser.parse_args(argv)
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
