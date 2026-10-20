# Run the self-tests:
#
#   python3 -m selftest [--program PATH] [--vs-code-adapter PATH] [--fail-on-skip] [--test ID]...
#                       [unittest options]
#   python3 -m selftest --list
#
# The root CMakeLists.txt builds the fixture program and registers each test --list prints as a
# CTest test, which runs it with --test. Tests whose requirements are missing (the fixture
# program, --vs-code-adapter, gdb, lldb-dap) are skipped. With --fail-on-skip, any skipped test
# makes the run fail.

import argparse
import os
import sys
import unittest

from . import test_integration

parser = argparse.ArgumentParser(prog="python3 -m selftest")
parser.add_argument("--program", metavar="PATH",
                    help="the built fixture program selftest/fixtures/prog.cpp")
parser.add_argument("--vs-code-adapter", metavar="PATH", help="path to OpenDebugAD7")
parser.add_argument("--fail-on-skip", action="store_true",
                    help="fail if any test is skipped, e.g. because a tool is missing")
parser.add_argument("--list", action="store_true", help="print the IDs of all tests and exit")
parser.add_argument("--test", metavar="ID", action="append", default=[],
                    help="run only the test with this ID (as --list prints it); repeatable")

ns, rest = parser.parse_known_args()
if ns.program:
    if not os.path.isfile(ns.program):
        parser.error(f"fixture program not found: {ns.program}")
    test_integration.PROGRAM = os.path.abspath(ns.program)
if ns.vs_code_adapter:
    if not os.path.isfile(ns.vs_code_adapter):
        parser.error(f"debug adapter not found: {ns.vs_code_adapter}")
    test_integration.ADAPTER = os.path.abspath(ns.vs_code_adapter)

here = os.path.dirname(os.path.abspath(__file__))

if ns.list:
    def test_ids(suite):
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                yield from test_ids(test)
            else:
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

success = program.result.wasSuccessful()
if ns.fail_on_skip and program.result.skipped:
    print(f"error: {len(program.result.skipped)} skipped:", file=sys.stderr)
    for test, reason in program.result.skipped:
        print(f"  {test}: {reason}", file=sys.stderr)
    success = False

sys.exit(0 if success else 1)
