# Run the self-tests: python3 -m selftest [--adapter PATH] [unittest options]
#
# Without --adapter only the tests that need no debugger run.

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
unittest.main(module=None, argv=[sys.argv[0], "discover", "-s", here,
                                 "-t", os.path.dirname(here)] + rest)
