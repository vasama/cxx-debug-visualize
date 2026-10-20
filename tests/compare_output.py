# Runs a command and compares its output with an expected output file, as the example's tests do
# (see examples/cmake/ExpectedOutputTests.cmake), for the tests that CMake registers:
#
#   python3 tests/compare_output.py EXPECTED ACTUAL COMMAND...
#
# Every hexadecimal number (0x...) in the output is replaced by "0x?", and line endings are ignored.
# If the output differs from EXPECTED (or that is missing), it is written to ACTUAL, with \n line
# endings, and a diff is printed. Exits with 1 if the command fails or the output differs.

import difflib
import os
import re
import subprocess
import sys

expected, actual, *command = sys.argv[1:]

# Text mode reads any line endings as \n.
run = subprocess.run(command, stdout=subprocess.PIPE, text=True, check=False)
output = re.sub(r"0x[0-9a-fA-F]+", "0x?", run.stdout)
expected_output = ""
if os.path.exists(expected):
    with open(expected) as f:
        expected_output = f.read()

failed = False
if output == expected_output:
    if os.path.exists(actual):
        os.remove(actual)
else:
    with open(actual, "w", newline="\n") as f:
        f.write(output)
    sys.stdout.writelines(
        difflib.unified_diff(
            expected_output.splitlines(True), output.splitlines(True), expected, actual
        )
    )
    if os.path.exists(expected):
        print(f"error: output differs from {expected} (actual output: {actual})", file=sys.stderr)
    else:
        print(
            f"error: expected output {expected} is missing (actual output: {actual})",
            file=sys.stderr,
        )
    failed = True
if run.returncode != 0:
    print(f"error: the command failed: exit status {run.returncode}", file=sys.stderr)
    failed = True

sys.exit(1 if failed else 0)
