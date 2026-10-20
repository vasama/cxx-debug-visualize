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
    def __init__(self, adapter, program, natvis, log=None):
        self.adapter = adapter
        self.program = os.path.abspath(program)
        self.natvis = os.path.abspath(natvis)
        # the program runs in its own directory
        self.cwd = os.path.dirname(self.program)
        self.log = log
        self.client = None
        self._children_cache = {}
        # breakpoint id -> state from the setBreakpoints reply (with "line" None),
        # before any "breakpoint" event updates it
        self._initial_breakpoint_states = {}

    # -- lifecycle -----------------------------------------------------------

    def launch_config(self):
        cfg = {
            "type": "cppdbg",
            "request": "launch",
            "name": "test_visualizers",
            "program": self.program,
            "cwd": self.cwd,
            # without miDebuggerPath, the adapter runs the gdb found on PATH
            "MIMode": "gdb",
            "externalConsole": False,
            "stopAtEntry": False,
            # VS Code's default (false) hides display strings and moves the
            # visualized children under a "[Visualized View]" node
            "showDisplayString": True,
            "logging": {"natvisDiagnostics": "warning", "moduleLoad": False},
            "visualizerFile": self.natvis,
        }
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

    # Set breakpoints; return the adapter's reply entries, with "line" None.
    #
    # The reply only echoes the requested lines, so "line" is cleared to keep it
    # from being mistaken for where a breakpoint really landed.
    def set_breakpoints(self, source, lines):
        body = self.client.request("setBreakpoints", {
            "source": {"path": source, "name": os.path.basename(source)},
            "breakpoints": [{"line": line} for line in lines],
        })
        breakpoints = body.get("breakpoints", [])
        for bp in breakpoints:
            bp["line"] = None
            self._initial_breakpoint_states[bp["id"]] = bp
        return breakpoints

    # Latest state of a breakpoint returned by set_breakpoints.
    #
    # That is the last "breakpoint" event about it, which has the line it really
    # landed on (e.g. moved to the next line with code); without one, the
    # setBreakpoints reply entry, whose "line" is None.
    def get_breakpoint(self, breakpoint_id):
        initial = self._initial_breakpoint_states[breakpoint_id]
        return self.client.breakpoints.get(breakpoint_id, initial)

    # Wait for the program to stop or end; return the DAP event.
    def wait_stop(self):
        return self.client.wait_event(("stopped", "terminated", "exited"))

    def resume(self, thread_id):
        self._children_cache.clear()
        self.client.request("continue", {"threadId": thread_id})

    def close(self):
        if self.client:
            self.client.close()

    # -- inspection ----------------------------------------------------------

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
        if node.ref not in self._children_cache:
            body = self.client.request("variables", {"variablesReference": node.ref})
            self._children_cache[node.ref] = [
                Node(v["name"], v.get("value", ""), v.get("type"), v.get("variablesReference", 0))
                for v in body.get("variables", [])
            ]
        return self._children_cache[node.ref]
