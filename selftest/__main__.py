# Run the self-tests: python3 -m selftest [--adapter PATH] [unittest options]
#
# Tests whose requirements are missing (--adapter, gdb, lldb-dap, a C++ compiler) are skipped, and
# any skipped test makes the run fail.

import argparse
import os
import sys
import unittest

from . import test_integration

parser = argparse.ArgumentParser(prog="python3 -m selftest")
parser.add_argument("--adapter", metavar="PATH", help="path to OpenDebugAD7")
ns, rest = parser.parse_known_args()
if ns.adapter:
    if not os.path.isfile(ns.adapter):
        parser.error(f"debug adapter not found: {ns.adapter}")
    test_integration.ADAPTER = os.path.abspath(ns.adapter)

here = os.path.dirname(os.path.abspath(__file__))
program = unittest.main(module=None, argv=[sys.argv[0], "discover", "-s", here,
                                           "-t", os.path.dirname(here)] + rest, exit=False)
result = program.result
if result.skipped:
    print(f"error: {len(result.skipped)} skipped:", file=sys.stderr)
    for test, reason in result.skipped:
        print(f"  {test}: {reason}", file=sys.stderr)
sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
