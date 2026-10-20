# A debug session driven like VS Code drives a "cppdbg" launch configuration.

import os

from .adapter import adapter_argv
from .dap import DapClient, DapError

# Natvis diagnostics (bad XML, unparsable type names, ...) arrive as debug
# console output such as "[Natvis] [Error] Error ... while reading file: ...".
_NATVIS_PREFIX = "[Natvis]"

# One row of the Variables/Watch tree.
class Node:
    def __init__(self, name, value, type_, ref):
        self.name = name
        self.value = value
        self.type = type_
        self.ref = ref

    @property
    def expandable(self):
        return self.ref > 0

class DebugSession:
    # The visualizer under test is either a natvis file or a gdb pretty-printer script. Exactly one
    # must be specified.
    def __init__(self, adapter, program, *, natvis=None, printers=None, log=None):
        if (natvis is None) == (printers is None):
            raise ValueError("exactly one of natvis or printers is required")

        self._adapter = adapter
        self._program = os.path.abspath(program)
        self._natvis = natvis and os.path.abspath(natvis)
        self._printers = printers and os.path.abspath(printers)
        self._log = log
        self._breakpoints = {}
        self._client = None
        self._natvis_diagnostics = []

    # -- Lifecycle -----------------------------------------------------------

    def _launch_config(self):
        cfg = {
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
    def _handle_event(self, event):
        match event:
            case {"event": "breakpoint", "body": {"breakpoint": {"id": bp_id} as bp}}:
                self._breakpoints[bp_id] = bp
            case {"event": "output", "body": {"category": "console", "output": text}}:
                if text.startswith(_NATVIS_PREFIX):
                    self._natvis_diagnostics.append(text)

    # Send a `setBreakpoints` request. Returns the adapter's reply entries.
    #
    # The reply only echoes the requested lines, so "line" is cleared to keep it from being mistaken
    # for where a breakpoint really landed.
    def _set_breakpoints(self, source, lines):
        body = self._client.request("setBreakpoints", {
            "source": {"path": source, "name": os.path.basename(source)},
            "breakpoints": [{"line": line} for line in lines],
        })

        breakpoints = body.get("breakpoints", [])
        for bp in breakpoints:
            bp["line"] = None
            # events are handled while waiting for the reply, so one may already be newer
            self._breakpoints.setdefault(bp["id"], bp)

        return [bp["id"] for bp in breakpoints]

    # Launch the program with `breakpoints` = {source path: [lines]}.
    #
    # Returns {source path: [resolved breakpoint dicts]} in request order.
    def start(self, breakpoints):
        self._client = DapClient(adapter_argv(self._adapter), log=self._log,
                                on_event=self._handle_event)
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
        launch_seq = self._client.request_async("launch", self._launch_config())
        self._client.wait_event("initialized", request_seq=launch_seq)
        resolved = {}
        for source, lines in breakpoints.items():
            resolved[source] = self._set_breakpoints(source, lines)
        self._client.request("configurationDone")
        self._client.wait_response(launch_seq)
        return resolved

    # Latest state of a breakpoint returned by _set_breakpoints.
    #
    # That is the last "breakpoint" event describing the specified breakpoint. If no event has been
    # received, the initial reply to `setBreakpoints` is returned.
    def get_breakpoint(self, breakpoint_id):
        return self._breakpoints[breakpoint_id]

    # Wait for the program to stop or exit. Returns the relevant DAP event.
    def wait_stop(self):
        return self._client.wait_event(("stopped", "terminated", "exited"))

    def resume(self, thread_id):
        self._client.request("continue", {"threadId": thread_id})

    def close(self):
        if self._client:
            self._client.close()

    def natvis_diagnostics(self):
        return self._natvis_diagnostics

    def stderr_output(self):
        return self._client.stderr_output() if self._client else ""

    # -- Inspection ----------------------------------------------------------

    def top_frame(self, thread_id):
        frames = self._client.request("stackTrace", {"threadId": thread_id, "startFrame": 0,
                                                    "levels": 1})["stackFrames"]
        if not frames:
            raise DapError(f"thread {thread_id} has no stack frames")
        return frames[0]

    def evaluate(self, expression, frame_id):
        body = self._client.request("evaluate", {"expression": expression, "frameId": frame_id,
                                                "context": "watch"})
        return Node(expression, body.get("result", ""), body.get("type"),
                    body.get("variablesReference", 0))

    def children(self, node):
        if not node.expandable:
            return []
        body = self._client.request("variables", {"variablesReference": node.ref})
        return [Node(v["name"], v.get("value", ""), v.get("type"), v.get("variablesReference", 0))
                for v in body.get("variables", [])]
