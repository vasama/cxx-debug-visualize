# Running natvis tests: break on check_visualizer() calls, print snapshots.
#
# Every line of the test source that consists of exactly `check_visualizer(x);`
# gets a breakpoint. Each time one is hit, the Variables tree of `x` is written
# to the output, for FileCheck to verify against the CHECK lines in the test
# source:
#
#     check_visualizer(v) at test_vector.cpp:12
#       { size=2 } [mylib::Vector<int>]
#         [size] = 2 [std::size_t]
#         [0] = 10 [int]
#         ...
#
# Errors the adapter reports (failed requests, unverified breakpoints, natvis
# diagnostics, anything it writes to its stderr besides its startup banner) are
# printed to stderr verbatim; test_visualizers's own errors (e.g. an unexpected stop)
# are prefixed with "error: ". Either fails the run. Everything else, including
# evaluation errors and calls that are never reached, shows up as output that
# differs from what the CHECK lines expect.

import os
import re
import sys

from .dap import AdapterError, DapError
from .session import DebugSession

CALL_RE = re.compile(r"^\s*check_visualizer\(\s*([A-Za-z_]\w*)\s*\)\s*;\s*$")

# Natvis diagnostics (bad XML, unparsable type names, ...) arrive as debug
# console output such as "[Natvis] [Error] Error ... while reading file: ...".
NATVIS_PREFIX = "[Natvis]"


# A `check_visualizer(identifier);` line in a test source.
class Call:
    def __init__(self, line, identifier):
        self.line = line
        self.identifier = identifier
        self.breakpoint_id = -1


def find_calls(path):
    calls = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for lineno, text in enumerate(f, 1):
            m = CALL_RE.match(text)
            if m:
                calls.append(Call(lineno, m.group(1)))
    return calls


class Runner:
    def __init__(self, adapter, program, source, natvis, log=None):
        self.adapter = adapter
        self.program = program
        self.source = os.path.abspath(source)
        self.natvis = os.path.abspath(natvis)
        self.log = log
        self.failed = False

    # Report an error found by test_visualizers itself.
    def _error(self, message):
        self.failed = True
        print(f"error: {message}", file=sys.stderr)

    # Pass on an error reported by the adapter, verbatim.
    def _report(self, text):
        self.failed = True
        sys.stderr.write(text if text.endswith("\n") else text + "\n")

    # Print `label = value [type]`, or just `value [type]` without a label.
    def _write_node(self, node, indent, label=None):
        type_ = f" [{node.type}]" if node.type else ""
        name = f"{label} = " if label is not None else ""
        print(f"{'  ' * indent}{name}{node.value}{type_}")

    # Write the children of `node`, i.e. what its type's visualizer produces.
    #
    # Children are not expanded further (their own children come from their own
    # types' visualizers), except "[More...]", which continues the same list.
    #
    # "[Raw View]" is listed but not expanded.
    def _write_children(self, session, node, indent):
        for kid in session.children(node):
            self._write_node(kid, indent, kid.name)
            if kid.name == "[More...]":
                self._write_children(session, kid, indent + 1)

    # Report and return False unless every breakpoint sits on its requested line.
    def _verify_breakpoints(self, session, calls):
        for call in calls:
            def _bp_error(message):
                self._error(f"{self.source}:{call.line}: {message}")

            bp = session.get_breakpoint(call.breakpoint_id)
            if not bp.get("verified"):
                if bp.get("message"):
                    self._report(bp["message"])
                else:
                    _bp_error("breakpoint could not be set")
                return False

            if bp.get("line") is None:
                _bp_error("breakpoint was not bound to any line")
                return False

            if bp["line"] != call.line:
                _bp_error(f"breakpoint landed on line "
                          f"{bp['line']} instead (no code on line {call.line}?)")
                return False

        return True

    # Print snapshots to stdout and errors to stderr; return True if no errors.
    def run(self):
        self.failed = False
        calls = find_calls(self.source)

        if not calls:
            return True

        session = DebugSession(self.adapter, self.program, self.natvis, log=self.log)
        try:
            resolved = session.start({self.source: [call.line for call in calls]})

            for call, bp in zip(calls, resolved[self.source]):
                call.breakpoint_id = bp["id"]

            # Every breakpoint must land on its own line; otherwise stop without
            # running any further. The adapter reports where breakpoints land
            # during startup, and they don't move afterwards.
            if not self._verify_breakpoints(session, calls):
                return False

            breakpoints_by_line = {call.line: call for call in calls}
            while True:
                event = session.wait_stop()
                if event["event"] != "stopped":
                    break

                body = event["body"]
                thread_id = body["threadId"]
                frame = session.top_frame(thread_id)
                source = frame.get("source", {}).get("path", self.program)

                if body["reason"] == "breakpoint" and frame["line"] in breakpoints_by_line:
                    call = breakpoints_by_line[frame["line"]]
                    print(f"check_visualizer({call.identifier}) at "
                          f"{os.path.basename(source)}:{call.line}")
                    node = session.evaluate(call.identifier, frame["id"])
                    self._write_node(node, 1)
                    self._write_children(session, node, 2)
                    sys.stdout.flush()
                else:
                    text = (body.get("text") or body.get("description") or body.get("reason"))
                    self._error(f"{source}:{frame['line']}: program stopped unexpectedly ({text}) "
                                f"in {frame['name']}")

                session.resume(thread_id)
        except AdapterError as e:
            self._report(str(e))
        except DapError as e:
            self._error(f"debug session: {e}")
        finally:
            session.close()
            if session.client:
                for category, text in session.client.output:
                    if category == "console" and text.startswith(NATVIS_PREFIX):
                        self._report(text)
                # anything else the adapter wrote to stderr is a failure too
                stderr = session.client.stderr_output()
                if stderr:
                    self._report(stderr)
        return not self.failed
