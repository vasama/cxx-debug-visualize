# Minimal Debug Adapter Protocol client.
#
# Talks to a debug adapter (here: OpenDebugAD7 from the VS Code C/C++ extension) over its
# stdin/stdout, the same way VS Code does. Everything runs on the caller's thread. Waiting for a
# response or an event reads protocol messages from the adapter's stdout until it has arrived.

import collections
import json
import os
import subprocess

# OpenDebugAD7 writes this line to stderr whenever it starts in stdio mode.
_BANNER = "waiting for v8 protocol on stdin/stdout"

# The debug session cannot continue, e.g. because the adapter exited.
class DapError(Exception):
    pass

# A request the adapter answered with an error; str() is its message.
class AdapterError(DapError):
    pass

class DapClient:
    # `on_event` is called with every event as soon as it arrives, before it is queued for
    # wait_event().
    def __init__(self, argv, log=None, on_event=None):
        env = dict(os.environ)
        env["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "1"

        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        self._seq = 0
        self._responses = {}
        self._events = collections.deque()
        self._stderr = None
        self._log = log
        self._on_event = on_event

    # -- Message handling ----------------------------------------------------

    def _handle_message(self, msg):
        if self._log:
            self._log("<- " + json.dumps(msg))

        match msg:
            case {"type": "response", "request_seq": seq}:
                self._responses[seq] = msg

            case {"type": "event"}:
                if self._on_event:
                    self._on_event(msg)
                self._events.append(msg)

            case {"type": "request", "seq": seq, "command": command}:
                # Reverse requests (e.g. runInTerminal) are not supported.
                self._send({
                    "type": "response",
                    "request_seq": seq,
                    "command": command,
                    "success": False,
                    "message": "not supported",
                })

    # -- Transport -----------------------------------------------------------

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

    # Read and handle the next message from the adapter.
    def _receive(self):
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

    # -- Public interface ----------------------------------------------------

    # Send a request without waiting for a response. Returns the message sequence number.
    def request_async(self, command, arguments=None):
        msg = {"type": "request", "command": command}
        if arguments is not None:
            msg["arguments"] = arguments
        return self._send(msg)

    # Wait for the response to a request sent with the specified sequence number.
    def wait_response(self, seq):
        while seq not in self._responses:
            self._receive()
        resp = self._responses.pop(seq)
        if not resp.get("success"):
            raise AdapterError(resp.get("message") or json.dumps(resp.get("body")))
        return resp.get("body") or {}

    def request(self, command, arguments=None):
        return self.wait_response(self.request_async(command, arguments))

    # Return the next event whose name is in `names`, discarding others.
    # If request `request_seq` fails in the meantime, raise its error instead.
    def wait_event(self, names, request_seq=None):
        if isinstance(names, str):
            names = (names,)

        while True:
            resp = self._responses.get(request_seq)
            if resp is not None and not resp.get("success"):
                self.wait_response(request_seq)
            while self._events:
                event = self._events.popleft()
                if event["event"] in names:
                    return event
            self._receive()

    # End the session and wait for the adapter to exit.
    def close(self):
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

            # Read whatever the adapter still sends, so that it never blocks writing to a pipe
            # nobody reads while shutting down.
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

    # What the adapter wrote to stderr (ignoring the MIEngine startup banner).
    #
    # Only available once close() has returned.
    def stderr_output(self):
        return "".join(line for line in self._stderr.splitlines(keepends=True)
                       if line.rstrip("\r\n") != _BANNER)
