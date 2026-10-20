"""Minimal Debug Adapter Protocol client.

Talks to a debug adapter (here: OpenDebugAD7 from the VS Code C/C++
extension) over its stdin/stdout, the same way VS Code does.  Everything runs
on the caller's thread: waiting for a response or an event reads protocol
messages from the adapter's stdout until it has arrived.
"""

import collections
import json
import os
import subprocess

# OpenDebugAD7 writes this line to stderr whenever it starts in stdio mode.
_BANNER = "waiting for v8 protocol on stdin/stdout"


class DapError(Exception):
    pass


class AdapterError(DapError):
    """A request the adapter answered with an error; str() is its message."""


class DapClient:
    def __init__(self, argv, env=None, log=None):
        # stderr stays in its pipe until the adapter has exited (see close());
        # the adapter writes next to nothing there.
        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        self._seq = 0
        self._responses = {}
        self._events = collections.deque()  # events not yet asked for
        self._stderr = ""
        self.output = []  # (category, text) of every "output" event
        self.breakpoints = {}  # id -> latest breakpoint from "breakpoint" events
        self._log = log

    # -- transport -----------------------------------------------------------

    def _read_message(self):
        headers = {}
        while True:
            line = self._proc.stdout.readline()
            if not line:
                return None
            line = line.decode("ascii").strip()
            if not line:
                break
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
        length = int(headers["content-length"])
        body = b""
        while len(body) < length:
            chunk = self._proc.stdout.read(length - len(body))
            if not chunk:
                return None
            body += chunk
        return json.loads(body)

    def _handle_message(self, msg):
        if self._log:
            self._log("<- " + json.dumps(msg))

        match msg:
            case {"type": "response", "request_seq": seq}:
                self._responses[seq] = msg
            case {"type": "event"}:
                match msg:
                    case {"event": "output", "body": body}:
                        self.output.append((body.get("category", ""), body.get("output", "")))
                    case {"event": "breakpoint", "body": {"breakpoint": {"id": bp_id} as bp}}:
                        self.breakpoints[bp_id] = bp
                self._events.append(msg)
            case {"type": "request", "seq": seq, "command": command}:
                # Reverse requests (e.g. runInTerminal) are not supported; we
                # launch with externalConsole=false so none should arrive.
                self._send({
                    "type": "response",
                    "request_seq": seq,
                    "command": command,
                    "success": False,
                    "message": "not supported",
                })

    def _receive(self):
        """Read and handle the next message from the adapter."""
        msg = self._read_message()
        if msg is None:
            raise DapError(f"debug adapter exited (code {self._proc.wait()})")
        self._handle_message(msg)

    def _send(self, msg):
        self._seq += 1
        msg["seq"] = self._seq

        if self._log:
            self._log("-> " + json.dumps(msg))

        data = json.dumps(msg).encode()
        self._proc.stdin.write(f"Content-Length: {len(data)}\r\n\r\n".encode() + data)
        self._proc.stdin.flush()

        return self._seq

    # -- requests / events ---------------------------------------------------

    def request_async(self, command, arguments=None):
        msg = {"type": "request", "command": command}
        if arguments is not None:
            msg["arguments"] = arguments
        return self._send(msg)

    def wait_response(self, seq):
        """Wait for the response to request `seq`."""
        while seq not in self._responses:
            self._receive()
        resp = self._responses.pop(seq)
        if not resp.get("success"):
            raise AdapterError(resp.get("message") or json.dumps(resp.get("body")))
        return resp.get("body") or {}

    def request(self, command, arguments=None):
        return self.wait_response(self.request_async(command, arguments))

    def wait_event(self, names, request_seq=None):
        """Return the next event whose name is in `names`, discarding others.

        If request `request_seq` fails in the meantime, raise its error instead
        (e.g. a failed `launch` never sends `initialized`).
        """
        if isinstance(names, str):
            names = (names,)
        while True:
            resp = self._responses.get(request_seq)
            if resp is not None and not resp.get("success"):
                self.wait_response(request_seq)  # raises the request's error
            while self._events:
                event = self._events.popleft()
                if event["event"] in names:
                    return event
            self._receive()

    def close(self):
        """End the session and wait for the adapter to exit.

        `disconnect` makes the adapter terminate the debuggee and shut down.
        Even without it (e.g. when natvistest is interrupted), closing the
        adapter's input ends the adapter, and gdb and the debuggee with it
        (see mi-engine-issue/ for the adapter fix this relies on).
        """
        try:
            if self._proc.poll() is None:
                self.request("disconnect", {"terminateDebuggee": True})
        except (DapError, OSError, ValueError):
            pass
        finally:
            try:
                self._proc.stdin.close()
            except (OSError, ValueError):
                pass
            # read whatever the adapter still sends, so that it never blocks
            # writing to a pipe nobody reads while shutting down
            try:
                while True:
                    msg = self._read_message()
                    if msg is None:
                        break
                    self._handle_message(msg)
            except (OSError, ValueError):
                pass
            self._proc.wait()
            self._stderr = self._proc.stderr.read().decode(errors="replace")
            for stream in (self._proc.stdout, self._proc.stderr):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass

    def stderr_output(self):
        """What the adapter wrote to stderr, without its startup banner.

        Available once close() has returned.
        """
        return "".join(line for line in self._stderr.splitlines(keepends=True)
                       if line.rstrip("\r\n") != _BANNER)


def default_env():
    env = dict(os.environ)
    # The adapter is a .NET app; avoid ICU dependency problems on minimal systems.
    env.setdefault("DOTNET_SYSTEM_GLOBALIZATION_INVARIANT", "1")
    return env
