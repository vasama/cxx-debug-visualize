# A debug session driven like VS Code drives a "cppdbg" launch configuration.

import os

from .adapter import adapter_argv
from .dap import DapClient, DapError

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

        self.adapter = adapter
        self.program = os.path.abspath(program)
        self.natvis = natvis and os.path.abspath(natvis)
        self.printers = printers and os.path.abspath(printers)
        self.log = log
        self.client = None
        self._initial_breakpoint_states = {}

    # -- Lifecycle -----------------------------------------------------------

    def launch_config(self):
        cfg = {
            "type": "cppdbg",
            "request": "launch",
            "name": "test_visualizers",
            "program": self.program,
            "cwd": os.path.dirname(self.program),
            "MIMode": "gdb",
            "externalConsole": False,
            "stopAtEntry": False,
            "logging": {"natvisDiagnostics": "warning", "moduleLoad": False},
        }

        if self.natvis:
            cfg["visualizerFile"] = self.natvis
            # VS Code's default (false) hides display strings and moves the
            # visualized children under a "[Visualized View]" node
            cfg["showDisplayString"] = True

        if self.printers:
            # gdb pretty printers, which don't mix with natvis.  Only the
            # printers under test are active: gdb reads no init files (-nx), and
            # auto-loaded printers (e.g. libstdc++'s) stay off.
            cfg["miDebuggerArgs"] = "-nx"
            cfg["setupCommands"] = [
                {"text": "-enable-pretty-printing"},
                {"text": "set auto-load python-scripts off"},
                {"text": f"source {self.printers}"},
            ]

        return cfg

    # Launch the program with `breakpoints` = {source path: [lines]}.
    #
    # Returns {source path: [resolved breakpoint dicts]} in request order.
    def start(self, breakpoints):
        self.client = DapClient(adapter_argv(self.adapter), log=self.log)
        self.client.request("initialize", {
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
        launch_seq = self.client.request_async("launch", self.launch_config())
        self.client.wait_event("initialized", request_seq=launch_seq)
        resolved = {}
        for source, lines in breakpoints.items():
            resolved[source] = self.set_breakpoints(source, lines)
        self.client.request("configurationDone")
        self.client.wait_response(launch_seq)
        return resolved

    # Send a `setBreakpoints` request. Returns the adapter's reply entries.
    #
    # The reply only echoes the requested lines, so "line" is cleared to keep it from being mistaken
    # for where a breakpoint really landed.
    def set_breakpoints(self, source, lines):
        body = self.client.request("setBreakpoints", {
            "source": {"path": source, "name": os.path.basename(source)},
            "breakpoints": [{"line": line} for line in lines],
        })

        breakpoints = body.get("breakpoints", [])
        for bp in breakpoints:
            bp["line"] = None
            self._initial_breakpoint_states[bp["id"]] = bp

        return [bp["id"] for bp in breakpoints]

    # Latest state of a breakpoint returned by set_breakpoints.
    #
    # That is the last "breakpoint" event describing the specified breakpoing. If no event has been
    # received, the initial reply to `setBreakpoints` is returned.
    def get_breakpoint(self, breakpoint_id):
        initial = self._initial_breakpoint_states[breakpoint_id]
        return self.client.breakpoints.get(breakpoint_id, initial)

    # Wait for the program to stop or exit. Returns the relevant DAP event.
    def wait_stop(self):
        return self.client.wait_event(("stopped", "terminated", "exited"))

    def resume(self, thread_id):
        self.client.request("continue", {"threadId": thread_id})

    def close(self):
        if self.client:
            self.client.close()

    # -- Inspection ----------------------------------------------------------

    def top_frame(self, thread_id):
        frames = self.client.request("stackTrace", {"threadId": thread_id, "startFrame": 0,
                                                    "levels": 1})["stackFrames"]
        if not frames:
            raise DapError(f"thread {thread_id} has no stack frames")
        return frames[0]

    def evaluate(self, expression, frame_id):
        body = self.client.request("evaluate", {"expression": expression, "frameId": frame_id,
                                                "context": "watch"})
        return Node(expression, body.get("result", ""), body.get("type"),
                    body.get("variablesReference", 0))

    def children(self, node):
        if not node.expandable:
            return []
        body = self.client.request("variables", {"variablesReference": node.ref})
        return [Node(v["name"], v.get("value", ""), v.get("type"), v.get("variablesReference", 0))
                for v in body.get("variables", [])]
