# Minimal Debug Adapter Protocol client.
#
# Talks to a debug adapter (here: OpenDebugAD7 from the VS Code C/C++ extension) over its
# stdin/stdout, the same way VS Code does. Everything runs on the caller's thread. Waiting for a
# response or an event reads protocol messages from the adapter's stdout until it has arrived.

import collections
import json
import os
import subprocess
from collections.abc import Callable
from typing import IO, Any

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
    def __init__(
        self,
        argv: list[str],
        log: Callable[[str], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        env = dict(os.environ)
        env["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "1"

        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        # All three are pipes, which Popen types as optional.
        assert self._proc.stdin and self._proc.stdout and self._proc.stderr
        self._stdin_pipe: IO[bytes] = self._proc.stdin
        self._stdout_pipe: IO[bytes] = self._proc.stdout
        self._stderr_pipe: IO[bytes] = self._proc.stderr

        self._seq: int = 0
        self._responses: dict[int, dict[str, Any]] = {}
        self._events: collections.deque[dict[str, Any]] = collections.deque()
        self._stderr: str | None = None
        self._log = log
        self._on_event = on_event

    # -- Message handling ----------------------------------------------------

    def _handle_message(self, msg: dict[str, Any]) -> None:
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
                self._send(
                    {
                        "type": "response",
                        "request_seq": seq,
                        "command": command,
                        "success": False,
                        "message": "not supported",
                    }
                )

    # -- Transport -----------------------------------------------------------

    def _read_message(self) -> dict[str, Any] | None:
        headers: dict[str, str] = {}
        while True:
            line_bytes = self._stdout_pipe.readline()
            if not line_bytes:
                return None
            line = line_bytes.decode("ascii").strip()
            if not line:
                break
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
        length = int(headers["content-length"])
        body = b""
        while len(body) < length:
            chunk = self._stdout_pipe.read(length - len(body))
            if not chunk:
                return None
            body += chunk
        return json.loads(body)

    # Read and handle the next message from the adapter.
    def _receive(self) -> None:
        msg = self._read_message()
        if msg is None:
            raise DapError(f"debug adapter exited (code {self._proc.wait()})")
        self._handle_message(msg)

    def _send(self, msg: dict[str, Any]) -> int:
        self._seq += 1
        msg["seq"] = self._seq

        if self._log:
            self._log("-> " + json.dumps(msg))

        data = json.dumps(msg).encode()
        self._stdin_pipe.write(f"Content-Length: {len(data)}\r\n\r\n".encode() + data)
        self._stdin_pipe.flush()

        return self._seq

    # -- Public interface ----------------------------------------------------

    # Send a request without waiting for a response. Returns the message sequence number.
    def request_async(self, command: str, arguments: dict[str, Any] | None = None) -> int:
        msg: dict[str, Any] = {"type": "request", "command": command}
        if arguments is not None:
            msg["arguments"] = arguments
        return self._send(msg)

    # Wait for the response to a request sent with the specified sequence number.
    def wait_response(self, seq: int) -> dict[str, Any]:
        while seq not in self._responses:
            self._receive()
        resp = self._responses.pop(seq)
        if not resp.get("success"):
            raise AdapterError(resp.get("message") or json.dumps(resp.get("body")))
        return resp.get("body") or {}

    def request(self, command: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.wait_response(self.request_async(command, arguments))

    # Return the next event whose name is in `names`, discarding others.
    # If request `request_seq` fails in the meantime, raise its error instead.
    def wait_event(
        self, names: str | tuple[str, ...], request_seq: int | None = None
    ) -> dict[str, Any]:
        if isinstance(names, str):
            names = (names,)

        while True:
            if request_seq is not None:
                resp = self._responses.get(request_seq)
                if resp is not None and not resp.get("success"):
                    self.wait_response(request_seq)
            while self._events:
                event = self._events.popleft()
                if event["event"] in names:
                    return event
            self._receive()

    # End the session and wait for the adapter to exit.
    def close(self) -> None:
        try:
            if self._proc.poll() is None:
                self.request("disconnect", {"terminateDebuggee": True})
        except (DapError, OSError, ValueError):
            pass
        finally:
            try:
                self._stdin_pipe.close()
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
            self._stderr = self._stderr_pipe.read().decode(errors="replace")

            for stream in (self._stdout_pipe, self._stderr_pipe):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass

    # What the adapter wrote to stderr (ignoring the MIEngine startup banner).
    #
    # Only available once close() has returned.
    def stderr_output(self) -> str:
        assert self._stderr is not None, "only available after close()"
        return "".join(
            line
            for line in self._stderr.splitlines(keepends=True)
            if line.rstrip("\r\n") != _BANNER
        )
