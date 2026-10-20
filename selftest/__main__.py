# Run the self-tests:
#
#   python3 -m selftest [--program PATH] [--vs-adapter PATH] [--no-vs] [--no-gdb]
#                       [--no-lldb] [--test ID]... [unittest options]
#   python3 -m selftest [--no-vs] [--no-gdb] [--no-lldb] --list
#
# The root CMakeLists.txt builds the fixture program and registers each test --list prints as a
# CTest test, which runs it with --test. The integration tests of the debuggers and adapter turned
# off with --no-vs, --no-gdb and --no-lldb are skipped, and left out of --list; the others fail if
# what they need (the fixture program, --vs-adapter, gdb, lldb-dap) is missing.

import argparse
import os
import sys
import unittest

from . import test_integration

parser = argparse.ArgumentParser(prog="python3 -m selftest")
parser.add_argument(
    "--program", metavar="PATH", help="the built fixture program selftest/fixtures/test_program.cpp"
)
parser.add_argument("--vs-adapter", metavar="PATH", help="path to OpenDebugAD7")
parser.add_argument(
    "--no-vs",
    action="store_true",
    help="skip the integration tests through the Visual Studio debug adapter",
)
parser.add_argument("--no-gdb", action="store_true", help="skip the integration tests with gdb")
parser.add_argument("--no-lldb", action="store_true", help="skip the integration tests with lldb")
parser.add_argument(
    "--list", action="store_true", help="print the IDs of the tests not turned off and exit"
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
if ns.vs_adapter:
    if not os.path.isfile(ns.vs_adapter):
        parser.error(f"debug adapter not found: {ns.vs_adapter}")
    test_integration.ADAPTER = os.path.abspath(ns.vs_adapter)
test_integration.DISABLE = {tool for tool in ("vs", "gdb", "lldb") if getattr(ns, f"no_{tool}")}

here = os.path.dirname(os.path.abspath(__file__))

if ns.list:

    def test_ids(suite):
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                yield from test_ids(test)
            elif not (isinstance(test, test_integration.FixtureTestCase) and test.turned_off()):
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
