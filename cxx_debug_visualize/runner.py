# Running visualizer tests: break on visualize() invocations, print variable visualization.
#
# A breakpoint is set on each line of the test source consisting of exactly `visualize(x);` (with
# any identifier accepted in place of `x`). Each time a breakpoint is hit, a visualization of `x` is
# written to stdout.
#
# Example output:
#     visualize(v) at test_vector.cpp:12
#       { size=2 } [mylib::Vector<int>]
#         [size] = 2 [std::size_t]
#         [0] = 10 [int]
#         ...
#
# Errors the adapter reports (failed requests, unverified breakpoints, natvis diagnostics, or
# anything else it writes to its stderr besides its startup banner) are printed to stderr verbatim.
# cxx-debug-visualize's own errors (e.g. an unexpected stop) are prefixed with "error: ". Either one
# fails the run.

import os
import re
import sys
from collections.abc import Callable

from .dap import AdapterError, DapError
from .session import DebugSession, VisualizationNode

INVOCATION_RE = re.compile(r"^\s*visualize\(\s*([A-Za-z_]\w*)\s*\)\s*;\s*$")


# Represents a `visualize(identifier);` line in a test source.
class TestInvocation:
    def __init__(self, line: int, identifier: str) -> None:
        self.line = line
        self.identifier = identifier
        self.breakpoint_id: int = -1


def discover_test_lines(path: str) -> list[TestInvocation]:
    invocations: list[TestInvocation] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for lineno, text in enumerate(f, 1):
            m = INVOCATION_RE.match(text)
            if m:
                invocations.append(TestInvocation(lineno, m.group(1)))
    return invocations


class Runner:
    # The visualizer under test is a natvis file, a gdb pretty-printer script or an lldb formatter
    # script. With `adapter` None, the debugger's native DAP support is used (see DebugSession).
    def __init__(
        self,
        adapter: str | None,
        adapter_path: str | None,
        source: str,
        program: str,
        program_args: list[str],
        *,
        debugger: str,
        debugger_path: str | None = None,
        natvis: str | None = None,
        gdb_printers: str | None = None,
        lldb_formatters: str | None = None,
        default_visualizers: bool = True,
        print_line_numbers: bool = False,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self._adapter = adapter
        self._adapter_path = adapter_path
        self._program = program
        self._source = os.path.abspath(source)
        self._debugger = debugger
        self._debugger_path = debugger_path
        self._program_args = program_args
        self._visualizer: dict[str, str | None] = {
            "natvis": natvis,
            "gdb_printers": gdb_printers,
            "lldb_formatters": lldb_formatters,
        }
        self._default_visualizers = default_visualizers
        self._print_line_numbers = print_line_numbers
        self._log = log
        self._failed = False

    # Report an error found by cxx-debug-visualize itself.
    def _error(self, message: str) -> None:
        print(f"error: {message}", file=sys.stderr)
        self._failed = True

    # Pass on an error reported by the adapter.
    def _report(self, text: str) -> None:
        sys.stderr.write(text if text.endswith("\n") else text + "\n")
        self._failed = True

    # Print `label = value [type]`, or `value [type]` without a label.
    def _write_node(self, node: VisualizationNode, indent: int, label: str | None = None) -> None:
        type_ = f" [{node.type}]" if node.type else ""
        name = f"{label} = " if label is not None else ""
        print(f"{'  ' * indent}{name}{node.value}{type_}")

    # Print the children of `node`, i.e. what its type's visualizer produces.
    #
    # Children are not expanded further (their own children come from their own types' visualizers).
    # natvis visualizations use paging with "[More...]" printed when a limit is exceeded. Whenever
    # "[More...]" is encountered, the remaining children are expanded, as if the list were unpaged.
    #
    # "[Raw View]" lines emitted by natvis visualizers are discarded.
    def _write_children(self, session: DebugSession, node: VisualizationNode, indent: int) -> None:
        for child in session.children(node):
            if child.name == "[Raw View]":
                continue
            if child.name == "[More...]":
                self._write_children(session, child, indent)
                continue
            self._write_node(child, indent, child.name)

    # Report and return false if any breakpoint was placed on a line other than the one requested.
    def _verify_breakpoints(self, session: DebugSession, invocations: list[TestInvocation]) -> bool:
        for invocation in invocations:

            def _bp_error(message: str) -> None:
                self._error(f"{self._source}:{invocation.line}: {message}")  # noqa: B023

            bp = session.get_breakpoint(invocation.breakpoint_id)
            if not bp.get("verified"):
                if bp.get("message"):
                    self._report(bp["message"])
                else:
                    _bp_error("breakpoint could not be set")
                return False

            if bp.get("line") is None:
                _bp_error("breakpoint was not bound to any line")
                return False

            if bp["line"] != invocation.line:
                _bp_error(
                    f"breakpoint landed on line "
                    f"{bp['line']} instead (no code on line {invocation.line}?)"
                )
                return False

        return True

    # Start a debug session, wait for the debuggee to stop at a breakpoint, and print the relevant
    # visualization to stdout. Finally, close the debug adapter.
    def run(self) -> bool:
        self._failed = False
        invocations = discover_test_lines(self._source)

        if not invocations:
            return True

        session = DebugSession(
            self._adapter,
            self._adapter_path,
            self._program,
            self._program_args,
            debugger=self._debugger,
            debugger_path=self._debugger_path,
            **self._visualizer,
            default_visualizers=self._default_visualizers,
            log=self._log,
        )
        try:
            breakpoint_ids = session.start(
                {self._source: [invocation.line for invocation in invocations]}
            )

            for invocation, breakpoint_id in zip(
                invocations, breakpoint_ids[self._source], strict=True
            ):
                invocation.breakpoint_id = breakpoint_id

            if not self._verify_breakpoints(session, invocations):
                return False

            breakpoints_by_line = {invocation.line: invocation for invocation in invocations}
            while True:
                event = session.wait_stop()
                if event["event"] != "stopped":
                    break

                body = event["body"]
                thread_id = body["threadId"]
                frame = session.top_frame(thread_id)
                source = frame.get("source", {}).get("path", self._program)

                if body["reason"] == "breakpoint" and frame["line"] in breakpoints_by_line:
                    invocation = breakpoints_by_line[frame["line"]]

                    line_string = ""
                    if self._print_line_numbers:
                        line_string = f":{invocation.line}"

                    print(
                        f"visualize({invocation.identifier}) at "
                        f"{os.path.basename(source)}{line_string}"
                    )
                    node = session.evaluate(invocation.identifier, frame["id"])
                    self._write_node(node, 1)
                    self._write_children(session, node, 2)
                    sys.stdout.flush()
                else:
                    text = body.get("text") or body.get("description") or body.get("reason")
                    self._error(
                        f"{source}:{frame['line']}: program stopped unexpectedly ({text}) "
                        f"in {frame['name']}"
                    )

                session.resume(thread_id)
        except AdapterError as e:
            self._report(str(e))
        except DapError as e:
            self._error(f"debug session: {e}")
        finally:
            session.close()

            for text in session.diagnostics():
                self._report(text)

            # Anything written to stderr by the adapter is considered a failure.
            stderr = session.stderr_output()
            if stderr:
                self._report(stderr)

        return not self._failed
