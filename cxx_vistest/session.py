# A debug session driven like VS Code drives a "cppdbg" launch configuration.

import os
from collections.abc import Callable
from typing import Any

from .adapter import adapter_argv, find_lldb_dap
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
    # The visualizer under test is a natvis file, a gdb pretty-printer script or an lldb formatter
    # script. Exactly one must be specified.
    #
    # With `adapter` None, the debugger's native DAP support is used instead of OpenDebugAD7
    # (`gdb -i dap`, or lldb-dap). In this mode natvis is not supported. lldb is only supported
    # this way.
    def __init__(self, adapter: str | None, program: str, *, debugger: str,
                 natvis: str | None = None, gdb_printers: str | None = None,
                 lldb_formatters: str | None = None,
                 log: Callable[[str], None] | None = None) -> None:
        # The command line rejects all of these.
        assert [natvis, gdb_printers, lldb_formatters].count(None) == 2, \
            "exactly one of natvis, gdb_printers or lldb_formatters is required"
        assert debugger in ("gdb", "lldb"), f"unknown debugger: {debugger}"
        assert adapter is not None or natvis is None, "native DAP does not support natvis"
        assert debugger != "lldb" or adapter is None, \
            "lldb is only supported through its native DAP support"
        assert gdb_printers is None or debugger == "gdb", "gdb_printers needs gdb"
        assert lldb_formatters is None or debugger == "lldb", "lldb_formatters needs lldb"

        self._adapter = adapter
        self._debugger = debugger
        self._program = os.path.abspath(program)
        self._natvis = natvis and os.path.abspath(natvis)
        self._gdb_printers = gdb_printers and os.path.abspath(gdb_printers)
        self._lldb_formatters = lldb_formatters and os.path.abspath(lldb_formatters)
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
        if self._debugger == "lldb":
            # Only the formatters under test are active. lldb-dap is instructed to read no init
            # files reads no init files, and any built-in C++ formatters (e.g. for libstdc++) are
            # disabled.
            return {
                "program": self._program,
                "cwd": os.path.dirname(self._program),
                "initCommands": [
                    "type category disable -l c++",
                    f"command script import {self._lldb_formatters}",
                ],
            }

        cfg: dict[str, Any] = {
            "type": "cppdbg",
            "request": "launch",
            "name": "cxx-vistest",
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

        if self._gdb_printers:
            # Only the printers under test are active. gdb is instructed to read no init files
            # (-nx) and auto-loading of printers (e.g. for libstdc++'s) is disabled.
            cfg["miDebuggerArgs"] = "-nx"
            cfg["setupCommands"] = [
                {"text": "-enable-pretty-printing"},
                {"text": "set auto-load python-scripts off"},
                {"text": f"source {self._gdb_printers}"},
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
    # being mistaken for where a breakpoint really landed. gdb's and lldb-dap's replies have the
    # real lines.
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
        elif self._debugger == "lldb":
            lldb_dap = find_lldb_dap()
            if lldb_dap is None:
                raise DapError("lldb-dap (or lldb-vscode) not found on PATH")
            argv = [lldb_dap]
        else:
            # As with OpenDebugAD7, only the printers under test are active. The program is loaded
            # up front, so that breakpoints are bound as soon as they are set.
            argv = [
                "gdb",
                "-q",
                "-nx",
                "-i", "dap",
                "-iex", "set auto-load python-scripts off",
                "-ex", f"source {self._gdb_printers}",
                self._program
            ]

        self._client_or_none = DapClient(argv, log=self._log, on_event=self._handle_event)
        self._client.request("initialize", {
            "clientID": "vscode",
            "clientName": "cxx-vistest",
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

        if self._adapter is None and self._debugger == "gdb":
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
