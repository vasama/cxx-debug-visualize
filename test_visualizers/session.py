# A debug session driven like VS Code drives a "cppdbg" launch configuration.

import os
from collections.abc import Callable
from typing import Any

from .adapter import adapter_argv
from .dap import DapClient, DapError

# Natvis diagnostics (bad XML, unparsable type names, ...) arrive as debug
# console output such as "[Natvis] [Error] Error ... while reading file: ...".
_NATVIS_PREFIX = "[Natvis]"

# One row of the Variables/Watch tree.
class VisualizationNode:
    def __init__(self, name: str, value: str, type_: str | None, ref: int) -> None:
        self.name = name
        self.value = value
        self.type = type_
        self.ref = ref

    @property
    def expandable(self) -> bool:
        return self.ref > 0

class DebugSession:
    # The visualizer under test is either a natvis file or a gdb pretty-printer script. Exactly one
    # must be specified.
    #
    # With `adapter` None, gdb's native DAP support is used instead of OpenDebugAD7. In this mode
    # natvis is not supported.
    def __init__(self, adapter: str | None, program: str, *, natvis: str | None = None,
                 printers: str | None = None,
                 log: Callable[[str], None] | None = None) -> None:
        if (natvis is None) == (printers is None):
            raise ValueError("exactly one of natvis or printers is required")
        if adapter is None and natvis is not None:
            raise ValueError("gdb does not support natvis")

        self._adapter = adapter
        self._program = os.path.abspath(program)
        self._natvis = natvis and os.path.abspath(natvis)
        self._printers = printers and os.path.abspath(printers)
        self._log = log
        self._breakpoints: dict[int, dict[str, Any]] = {}
        self._client_or_none: DapClient | None = None
        self._natvis_diagnostics: list[str] = []

    # The client of a started session.
    @property
    def _client(self) -> DapClient:
        assert self._client_or_none is not None, "start() has not been called"
        return self._client_or_none

    # -- Lifecycle -----------------------------------------------------------

    def _launch_config(self) -> dict[str, Any]:
        cfg: dict[str, Any] = {
            "type": "cppdbg",
            "request": "launch",
            "name": "test_visualizers",
            "program": self._program,
            "cwd": os.path.dirname(self._program),
            "MIMode": "gdb",
            "externalConsole": False,
            "stopAtEntry": False,
            "logging": {"natvisDiagnostics": "warning", "moduleLoad": False},
        }

        if self._natvis:
            cfg["visualizerFile"] = self._natvis

            # MIEngine follows VS Code's default of hiding display strings, and moves the visualized
            # children under a "[Visualized View]" node. This is not desirable for testing purposes.
            cfg["showDisplayString"] = True

        if self._printers:
            # Only the printers under test are active. gdb is insutrcted to read no init files
            # (-nx) and auto-loading of printers (e.g. libstdc++'s) is disabled.
            cfg["miDebuggerArgs"] = "-nx"
            cfg["setupCommands"] = [
                {"text": "-enable-pretty-printing"},
                {"text": "set auto-load python-scripts off"},
                {"text": f"source {self._printers}"},
            ]

        return cfg

    # Called by the client with every event as it arrives.
    def _handle_event(self, event: dict[str, Any]) -> None:
        match event:
            case {"event": "breakpoint", "body": {"breakpoint": {"id": bp_id} as bp}}:
                self._breakpoints[bp_id] = bp
            case {"event": "output", "body": {"category": "console", "output": text}}:
                if text.startswith(_NATVIS_PREFIX):
                    self._natvis_diagnostics.append(text)

    # Send a `setBreakpoints` request. Returns the adapter's reply entries.
    #
    # OpenDebugAD7's reply only echoes the requested lines, so "line" is cleared to keep it from
    # being mistaken for where a breakpoint really landed. gdb's reply has the real lines.
    def _set_breakpoints(self, source: str, lines: list[int]) -> list[int]:
        body = self._client.request("setBreakpoints", {
            "source": {"path": source, "name": os.path.basename(source)},
            "breakpoints": [{"line": line} for line in lines],
        })

        breakpoints = body.get("breakpoints", [])
        for bp in breakpoints:
            if self._adapter is not None:
                bp["line"] = None
            # events are handled while waiting for the reply, so one may already be newer
            self._breakpoints.setdefault(bp["id"], bp)

        return [bp["id"] for bp in breakpoints]

    # Launch the program with `breakpoints` = {source path: [lines]}.
    #
    # Returns {source path: [resolved breakpoint dicts]} in request order.
    def start(self, breakpoints: dict[str, list[int]]) -> dict[str, list[int]]:
        if self._adapter is not None:
            argv = adapter_argv(self._adapter)
        else:
            # As with OpenDebugAD7, only the printers under test are active. The program is loaded
            # up front, so that breakpoints are bound as soon as they are set.
            argv = [
                "gdb",
                "-q",
                "-nx",
                "-i", "dap",
                "-iex", "set auto-load python-scripts off",
                "-ex", f"source {self._printers}",
                self._program
            ]

        self._client_or_none = DapClient(argv, log=self._log, on_event=self._handle_event)
        self._client.request("initialize", {
            "clientID": "vscode",
            "clientName": "test_visualizers",
            "adapterID": "cppdbg",
            "pathFormat": "path",
            "linesStartAt1": True,
            "columnsStartAt1": True,
            "supportsVariableType": True,
            "supportsVariablePaging": True,
            "supportsRunInTerminalRequest": False,
            "locale": "en-us",
        })
        resolved: dict[str, list[int]] = {}

        if self._adapter is None:
            # gdb runs the program as soon as it is launched, so it is configured first.
            self._client.wait_event("initialized")
            for source, lines in breakpoints.items():
                resolved[source] = self._set_breakpoints(source, lines)
            self._client.request("configurationDone")
            self._client.request("launch", {"cwd": os.path.dirname(self._program)})
            return resolved

        launch_seq = self._client.request_async("launch", self._launch_config())
        self._client.wait_event("initialized", request_seq=launch_seq)
        for source, lines in breakpoints.items():
            resolved[source] = self._set_breakpoints(source, lines)
        self._client.request("configurationDone")
        self._client.wait_response(launch_seq)
        return resolved

    # Latest state of a breakpoint returned by _set_breakpoints.
    #
    # That is the last "breakpoint" event describing the specified breakpoint. If no event has been
    # received, the initial reply to `setBreakpoints` is returned.
    def get_breakpoint(self, breakpoint_id: int) -> dict[str, Any]:
        return self._breakpoints[breakpoint_id]

    # Wait for the program to stop or exit. Returns the relevant DAP event.
    def wait_stop(self) -> dict[str, Any]:
        return self._client.wait_event(("stopped", "terminated", "exited"))

    def resume(self, thread_id: int) -> None:
        self._client.request("continue", {"threadId": thread_id})

    def close(self) -> None:
        if self._client_or_none:
            self._client_or_none.close()

    def natvis_diagnostics(self) -> list[str]:
        return self._natvis_diagnostics

    def stderr_output(self) -> str:
        return self._client_or_none.stderr_output() if self._client_or_none else ""

    # -- Inspection ----------------------------------------------------------

    def top_frame(self, thread_id: int) -> dict[str, Any]:
        frames = self._client.request("stackTrace", {"threadId": thread_id, "startFrame": 0,
                                                    "levels": 1})["stackFrames"]
        if not frames:
            raise DapError(f"thread {thread_id} has no stack frames")
        return frames[0]

    def evaluate(self, expression: str, frame_id: int) -> VisualizationNode:
        body = self._client.request("evaluate", {"expression": expression, "frameId": frame_id,
                                                "context": "watch"})
        return VisualizationNode(expression, body.get("result", ""), body.get("type"),
                                 body.get("variablesReference", 0))

    def children(self, node: VisualizationNode) -> list[VisualizationNode]:
        if not node.expandable:
            return []
        body = self._client.request("variables", {"variablesReference": node.ref})
        return [VisualizationNode(v["name"], v.get("value", ""), v.get("type"),
                                  v.get("variablesReference", 0))
                for v in body.get("variables", [])]
