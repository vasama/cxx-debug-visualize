# A debug session driven like VS Code drives a "cppdbg" launch configuration.

import os
from collections.abc import Callable
from typing import Any

from .adapter import find_lldb_dap, miengine_argv
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
    # script. At most one may be specified; without one, only the default visualizers are active.
    #
    # `adapter_path` is the path of the debug adapter executable (e.g. OpenDebugAD7). When
    # `adapter_path` is None, the debugger's native DAP support is used instead (`gdb -i dap`, or
    # lldb-dap).
    #
    # `debugger_path` is the debugger to use instead of the one found on PATH.
    #
    # With `default_visualizers` False, only the visualizer under test is active, not the ones the
    # debugger loads by default (e.g. libstdc++'s pretty printers, lldb's C++ formatters).
    def __init__(
        self,
        adapter: str | None,
        adapter_path: str | None,
        program: str,
        program_args: list[str],
        *,
        debugger: str,
        debugger_path: str | None = None,
        natvis: str | None = None,
        gdb_printers: str | None = None,
        lldb_formatters: str | None = None,
        default_visualizers: bool = True,
        log: Callable[[str], None] | None = None,
    ) -> None:
        # The command line rejects all of these.
        assert [natvis, gdb_printers, lldb_formatters].count(None) >= 2, (
            "at most one of natvis, gdb_printers or lldb_formatters may be specified"
        )
        assert default_visualizers or [natvis, gdb_printers, lldb_formatters].count(None) == 2, (
            "without the default visualizers, a visualizer under test is required"
        )
        assert (adapter is None) == (adapter_path is None), (
            "adapter type and path must be specified together"
        )
        assert debugger in ("gdb", "lldb", "dbgeng"), f"unknown debugger: {debugger}"
        assert natvis is None or adapter is not None, "native DAP does not support natvis"
        assert debugger != "dbgeng" or adapter is not None, (
            "dbgeng is only supported through an adapter"
        )
        assert debugger != "lldb" or adapter is None, (
            "lldb is only supported through its native DAP support"
        )
        assert natvis is None or adapter == "miengine" or debugger == "dbgeng", (
            "natvis needs MIEngine or dbgeng"
        )
        assert gdb_printers is None or debugger == "gdb", "gdb_printers needs gdb"
        assert lldb_formatters is None or debugger == "lldb", "lldb_formatters needs lldb"

        self._adapter = adapter
        self._adapter_path = adapter_path
        self._debugger = debugger
        self._debugger_path = debugger_path
        self._program = os.path.abspath(program)
        self._program_args = program_args
        self._natvis = natvis and os.path.abspath(natvis)
        self._gdb_printers = gdb_printers and os.path.abspath(gdb_printers)
        self._lldb_formatters = lldb_formatters and os.path.abspath(lldb_formatters)
        self._default_visualizers = default_visualizers
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
        if self._debugger == "dbgeng":
            config: dict[str, Any] = {
                "program": self._program,
                "args": self._program_args,
                "cwd": os.path.dirname(self._program),
                "defaultVisualizers": self._default_visualizers,
            }
            if self._natvis:
                config["visualizerFile"] = self._natvis
            if self._debugger_path:
                config["debuggerPath"] = self._debugger_path
            return config

        if self._debugger == "lldb":
            # Without the default visualizers, lldb's built-in C++ formatters (e.g. for libstdc++)
            # are disabled before the script is loaded.
            init_commands = []
            if not self._default_visualizers:
                init_commands.append("type category disable -l c++")
            if self._lldb_formatters:
                init_commands.append(f"command script import {self._lldb_formatters}")
            return {
                "program": self._program,
                "args": self._program_args,
                "cwd": os.path.dirname(self._program),
                "initCommands": init_commands,
            }

        cfg: dict[str, Any] = {
            "type": "cppdbg",
            "request": "launch",
            "name": "cxx-debug-visualize",
            "program": self._program,
            "args": self._program_args,
            "cwd": os.path.dirname(self._program),
            "MIMode": "gdb",
            "externalConsole": False,
            "stopAtEntry": False,
            "logging": {"natvisDiagnostics": "warning", "moduleLoad": False},
            "miDebuggerArgs": "-nx",
        }

        if self._debugger_path:
            cfg["miDebuggerPath"] = self._debugger_path

        if self._natvis:
            cfg["visualizerFile"] = self._natvis

            # MIEngine follows VS Code's default of hiding display strings, and moves the visualized
            # children under a "[Visualized View]" node. This is not desirable for testing purposes.
            cfg["showDisplayString"] = True

        # Pretty printing is enabled for the printers under test, and as in VS Code's default
        # configuration, for those gdb loads by default (e.g. libstdc++'s), which with natvis show
        # what natvis does not. Without the default visualizers, auto-loading of printers is
        # disabled.
        if self._gdb_printers or self._default_visualizers:
            cfg["setupCommands"] = [{"text": "-enable-pretty-printing"}]
            if not self._default_visualizers:
                cfg["setupCommands"].append({"text": "set auto-load python-scripts off"})
            if self._gdb_printers:
                cfg["setupCommands"].append({"text": f"source {self._gdb_printers}"})

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
    # being mistaken for where a breakpoint really landed. Otherwise, the reply is expected to
    # contain the actual line.
    def _set_breakpoints(self, source: str, lines: list[int]) -> list[int]:
        body = self._client.request(
            "setBreakpoints",
            {
                "source": {"path": source, "name": os.path.basename(source)},
                "breakpoints": [{"line": line} for line in lines],
            },
        )

        breakpoints = body.get("breakpoints", [])
        for bp in breakpoints:
            if self._adapter == "miengine":
                bp["line"] = None

            # Events are handled while waiting for the reply, so a more recent entry may already
            # exist.
            self._breakpoints.setdefault(bp["id"], bp)

        return [bp["id"] for bp in breakpoints]

    # Launch the program with `breakpoints` = {source path: [lines]}.
    #
    # Returns {source path: [resolved breakpoint dicts]} in request order.
    def start(self, breakpoints: dict[str, list[int]]) -> dict[str, list[int]]:
        if self._adapter is not None:
            assert self._adapter_path is not None

            if self._adapter == "miengine":
                argv = miengine_argv(self._adapter_path)
            else:
                argv = [self._adapter_path]
        elif self._debugger == "lldb":
            lldb_dap = self._debugger_path or find_lldb_dap()
            if lldb_dap is None:
                raise DapError("lldb-dap (or lldb-vscode) not found on PATH")
            argv = [lldb_dap]
        else:
            # As with OpenDebugAD7, gdb reads no init files, and without the default visualizers
            # loads no printers but those under test. The program is loaded up front, so that
            # breakpoints are bound as soon as they are set.
            argv = [self._debugger_path or "gdb", "-q", "-nx", "-i", "dap"]
            if not self._default_visualizers:
                argv += ["-iex", "set auto-load python-scripts off"]
            if self._gdb_printers:
                argv += ["-ex", f"source {self._gdb_printers}"]
            argv.append(self._program)

        self._client_or_none = DapClient(argv, log=self._log, on_event=self._handle_event)
        self._client.request(
            "initialize",
            {
                "clientID": "vscode",
                "clientName": "cxx-debug-visualize",
                "adapterID": "cppdbg",
                "pathFormat": "path",
                "linesStartAt1": True,
                "columnsStartAt1": True,
                "supportsVariableType": True,
                "supportsVariablePaging": True,
                "supportsRunInTerminalRequest": False,
                "locale": "en-us",
            },
        )
        resolved: dict[str, list[int]] = {}

        if self._adapter is None and self._debugger == "gdb":
            # Correctly functioning adapters send "initialized" in response to "launch", and only
            # run the program after "configurationDone", as the DAP specification intends. GDB 14
            # and 15 instead send "initialized" right after "initialize", and run the program as
            # soon as "launch" arrives, after which "configurationDone" fails with "notStopped"
            # because the program is running. So gdb is configured first and launched last.
            #
            # GDB 16 fixed this: "launch" may be sent at any time after "initialized", but does not
            # take effect (or send its response) until "configurationDone" has been sent.
            self._client.wait_event("initialized")
            for source, lines in breakpoints.items():
                resolved[source] = self._set_breakpoints(source, lines)
            self._client.request("configurationDone")
            self._client.request(
                "launch", {"cwd": os.path.dirname(self._program), "args": self._program_args}
            )
            return resolved
        else:
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
        frames = self._client.request(
            "stackTrace", {"threadId": thread_id, "startFrame": 0, "levels": 1}
        )["stackFrames"]
        if not frames:
            raise DapError(f"thread {thread_id} has no stack frames")
        return frames[0]

    def evaluate(self, expression: str, frame_id: int) -> VisualizationNode:
        body = self._client.request(
            "evaluate", {"expression": expression, "frameId": frame_id, "context": "watch"}
        )
        return VisualizationNode(
            expression, body.get("result", ""), body.get("type"), body.get("variablesReference", 0)
        )

    def children(self, node: VisualizationNode) -> list[VisualizationNode]:
        if not node.expandable:
            return []
        body = self._client.request("variables", {"variablesReference": node.ref})
        return [
            VisualizationNode(
                v["name"], v.get("value", ""), v.get("type"), v.get("variablesReference", 0)
            )
            for v in body.get("variables", [])
        ]
