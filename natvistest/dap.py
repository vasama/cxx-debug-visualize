"""Minimal Debug Adapter Protocol client.

Talks to a debug adapter (here: OpenDebugAD7 from the VS Code C/C++
extension) over its stdin/stdout, the same way VS Code does.
"""

import json
import os
import queue
import subprocess
import threading

# How often blocking waits wake up to check that the adapter is still alive.
_POLL_INTERVAL = 0.5


class DapError(Exception):
    pass


class AdapterError(DapError):
    """A request the adapter answered with an error; str() is its message."""


class DapClient:
    def __init__(self, argv, env=None, log=None):
        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        self._seq = 0
        self._lock = threading.Lock()
        self._responses = {}
        self._response_cv = threading.Condition()
        self.events = queue.Queue()
        self.output = []  # (category, text) of every "output" event
        self.breakpoints = {}  # id -> latest breakpoint from "breakpoint" events
        self._log = log
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._stderr = []
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    # -- transport -----------------------------------------------------------

    def _drain_stderr(self):
        for line in self._proc.stderr:
            self._stderr.append(line.decode(errors="replace"))

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

    def _read_loop(self):
        while True:
            msg = self._read_message()
            if msg is None:
                with self._response_cv:
                    self._response_cv.notify_all()
                self.events.put(None)
                return
            if self._log:
                self._log("<- " + json.dumps(msg))
            kind = msg.get("type")
            if kind == "response":
                with self._response_cv:
                    self._responses[msg["request_seq"]] = msg
                    self._response_cv.notify_all()
            elif kind == "event":
                body = msg.get("body", {})
                if msg["event"] == "output":
                    self.output.append((body.get("category", ""), body.get("output", "")))
                elif msg["event"] == "breakpoint" and "id" in body.get("breakpoint", {}):
                    self.breakpoints[body["breakpoint"]["id"]] = body["breakpoint"]
                self.events.put(msg)
            elif kind == "request":
                # Reverse requests (e.g. runInTerminal) are not supported; we
                # launch with externalConsole=false so none should arrive.
                self._send({
                    "type": "response",
                    "request_seq": msg["seq"],
                    "command": msg["command"],
                    "success": False,
                    "message": "not supported",
                })

    def _send(self, msg):
        with self._lock:
            self._seq += 1
            msg["seq"] = self._seq
            data = json.dumps(msg).encode()
            if self._log:
                self._log("-> " + json.dumps(msg))
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
        with self._response_cv:
            while seq not in self._responses:
                if self._proc.poll() is not None:
                    stderr = "".join(self._stderr[-20:])
                    raise DapError(f"debug adapter exited (code {self._proc.returncode}): {stderr}")
                self._response_cv.wait(_POLL_INTERVAL)
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
            if request_seq is not None:
                with self._response_cv:
                    resp = self._responses.get(request_seq)
                if resp is not None and not resp.get("success"):
                    self.wait_response(request_seq)  # raises the request's error
            try:
                ev = self.events.get(timeout=_POLL_INTERVAL)
            except queue.Empty:
                continue
            if ev is None:
                stderr = "".join(self._stderr[-20:])
                raise DapError(f"debug adapter closed the connection: {stderr}")
            if ev["event"] in names:
                return ev

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
            self._proc.wait()
            self._reader.join()
            for stream in (self._proc.stdout, self._proc.stderr):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass


def default_env():
    env = dict(os.environ)
    # The adapter is a .NET app; avoid ICU dependency problems on minimal systems.
    env.setdefault("DOTNET_SYSTEM_GLOBALIZATION_INVARIANT", "1")
    return env
