# Run the self-tests: python3 -m selftest [--adapter PATH] [--fail-on-skip] [unittest options]
#
# Tests whose requirements are missing (--adapter, gdb, lldb-dap, a C++ compiler) are skipped. With
# --fail-on-skip, any skipped test makes the run fail.

import argparse
import os
import sys
import unittest

from . import test_integration

parser = argparse.ArgumentParser(prog="python3 -m selftest")
parser.add_argument("--adapter", metavar="PATH", help="path to OpenDebugAD7")
parser.add_argument("--fail-on-skip", action="store_true",
                    help="fail if any test is skipped, e.g. because a tool is missing")

ns, rest = parser.parse_known_args()
if ns.adapter:
    if not os.path.isfile(ns.adapter):
        parser.error(f"debug adapter not found: {ns.adapter}")
    test_integration.ADAPTER = os.path.abspath(ns.adapter)

here = os.path.dirname(os.path.abspath(__file__))
program = unittest.main(module=None, argv=[sys.argv[0], "discover", "-s", here,
                                           "-t", os.path.dirname(here)] + rest, exit=False)

success = program.result.wasSuccessful()
if ns.fail_on_skip and program.result.skipped:
    print(f"error: {len(program.result.skipped)} skipped:", file=sys.stderr)
    for test, reason in program.result.skipped:
        print(f"  {test}: {reason}", file=sys.stderr)
    success = False

sys.exit(0 if success else 1)
