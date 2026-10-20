# Run the self-tests:
#
#   python3 -m tests [--program PATH] [--gdb PATH] [--lldb-dap PATH] [--miengine PATH]
#                       [--test ID]... [unittest options]
#   python3 -m tests [--gdb PATH] [--lldb-dap PATH] [--miengine PATH] --list
#
# The root CMakeLists.txt builds the fixture program and registers each test --list prints as a
# CTest test, which runs it with --test. The integration tests run with the executables given with
# --gdb, --lldb-dap and --miengine; those that need one not given are skipped, and left out of
# --list. Without the fixture program (--program), the integration tests fail.

import argparse
import os
import sys
import unittest

from . import test_integration

parser = argparse.ArgumentParser(prog="python3 -m tests")
parser.add_argument(
    "--program", metavar="PATH", help="the built fixture program tests/fixtures/test_program.cpp"
)
parser.add_argument("--gdb", metavar="PATH", help="gdb, to run the integration tests with")
parser.add_argument(
    "--lldb-dap", metavar="PATH", help="lldb-dap (or lldb-vscode), to run the lldb tests with"
)
parser.add_argument(
    "--miengine",
    metavar="PATH",
    help="OpenDebugAD7, MIEngine's debug adapter, to run tests through (with --gdb)",
)
parser.add_argument(
    "--list",
    action="store_true",
    help="print the IDs of the tests that the executables given allow and exit",
)
parser.add_argument(
    "--test",
    metavar="ID",
    action="append",
    default=[],
    help="run only the test with this ID (as --list prints it); repeatable",
)

ns, rest = parser.parse_known_args()
if ns.program:
    if not os.path.isfile(ns.program):
        parser.error(f"fixture program not found: {ns.program}")
    test_integration.PROGRAM = os.path.abspath(ns.program)
for tool in test_integration.TOOLS:
    path = getattr(ns, tool.replace("-", "_"))
    if path:
        if not os.path.isfile(path):
            parser.error(f"--{tool}: not found: {path}")
        test_integration.TOOLS[tool] = os.path.abspath(path)

here = os.path.dirname(os.path.abspath(__file__))

if ns.list:

    def test_ids(suite):
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                yield from test_ids(test)
            elif not (isinstance(test, test_integration.FixtureTestCase) and test.missing()):
                yield test.id()

    tests = unittest.defaultTestLoader.discover(here, top_level_dir=os.path.dirname(here))
    for test_id in test_ids(tests):
        print(test_id)
    sys.exit(0)

# All tests, or the ones given with --test, loaded by name.
if ns.test:
    argv = [sys.argv[0]] + rest + ns.test
else:
    argv = [sys.argv[0], "discover", "-s", here, "-t", os.path.dirname(here)] + rest
program = unittest.main(module=None, argv=argv, exit=False)
sys.exit(0 if program.result.wasSuccessful() else 1)
