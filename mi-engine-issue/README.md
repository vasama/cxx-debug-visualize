# OpenDebugAD7 keeps running after its input stream closes, leaving gdb and the debuggee running

*Draft issue for [microsoft/MIEngine](https://github.com/microsoft/MIEngine/issues). The reproduction script is `repro.sh` in this directory.*

---

## Summary

When a client closes OpenDebugAD7's stdin without sending `disconnect` (for
example because the client crashed or was killed), OpenDebugAD7 does not
exit. gdb and the program being debugged keep running with it,
indefinitely.

## Environment

- MIEngine `main` at
  [`fdd4552`](https://github.com/microsoft/MIEngine/commit/fdd455222c3233daf55143b027870639e13f7108),
  built with `PublishOpenDebugAD7.sh -c Release`. Also reproduced with the
  OpenDebugAD7 shipped in vscode-cpptools 1.34.4 (linux-x64).
- GNU gdb 15.1, Ubuntu 24.04, x86-64.

## Steps to reproduce

`repro.sh` pipes `initialize`, `launch` (`/bin/sleep 12345` under gdb) and
`configurationDone` into OpenDebugAD7. Five seconds later the pipe closes,
without a `disconnect` request, and ten seconds after that the script lists
what is still running:

```bash
#!/bin/bash
# OpenDebugAD7 keeps running, with gdb and the debuggee, after its stdin closes.
# Usage: ./repro.sh /path/to/OpenDebugAD7   (leaves the processes running; kill them afterwards)
send() { printf 'Content-Length: %d\r\n\r\n%s' ${#1} "$1"; }
{
  send '{"seq":1,"type":"request","command":"initialize","arguments":{"adapterID":"cppdbg","pathFormat":"path"}}'
  send '{"seq":2,"type":"request","command":"launch","arguments":{"program":"/bin/sleep","args":["12345"],"cwd":"/","MIMode":"gdb"}}'
  send '{"seq":3,"type":"request","command":"configurationDone"}'
  sleep 5
} | "$1" &> /dev/null &
sleep 15
echo "stdin closed 10s ago, still running:"
pgrep -a -x OpenDebugAD7; pgrep -a -x gdb; pgrep -a -f 'sleep 12345'
```

```
$ ./repro.sh /path/to/OpenDebugAD7
stdin closed 10s ago, still running:
2701470 /path/to/OpenDebugAD7
2701486 /usr/bin/gdb --interpreter=mi
2701501 /usr/bin/sleep 12345
```

For comparison, adding
`send '{"seq":4,"type":"request","command":"disconnect","arguments":{}}'`
after `sleep 5` makes all three processes exit, and the script lists nothing.

Both results are the same for the source build and for the cpptools 1.34.4
binary.

## Expected behavior

When its input stream ends, OpenDebugAD7 should end the session as it does
for `disconnect`, and then exit. For a launched debuggee, the
[`disconnect` request](https://microsoft.github.io/debug-adapter-protocol/specification#Requests_Disconnect)
is specified as follows: the debug adapter "must terminate the debuggee if it
was started with the `launch` request" and then "shut down itself".

A closed input stream means no client will ever send `disconnect`, so
treating it the same way seems the only useful behavior. When OpenDebugAD7
itself exits, gdb sees EOF on its input, quits, and kills the program it
launched. I checked this by killing OpenDebugAD7 directly: gdb and the
debuggee then exited on their own.

## Actual behavior

OpenDebugAD7, gdb and the debuggee all keep running. Nothing will ever talk
to them again.

## Analysis

In stdio mode, `Main` calls `Dispatch`, which runs the protocol loop and waits
for the reader
([Program.cs L179](https://github.com/microsoft/MIEngine/blob/fdd455222c3233daf55143b027870639e13f7108/src/OpenDebugAD7/OpenDebug/Program.cs#L179),
[L226-L232](https://github.com/microsoft/MIEngine/blob/fdd455222c3233daf55143b027870639e13f7108/src/OpenDebugAD7/OpenDebug/Program.cs#L226-L232)):

```csharp
AD7DebugSession debugSession = new AD7DebugSession(inputStream, outputStream, loggingCategories);

debugSession.Protocol.Run();
debugSession.Protocol.WaitForReader();
```

When stdin reaches EOF, the reader ends, `Dispatch` returns and `Main`
returns 0. Nothing on this path shuts the debug engine down, though.
`Protocol.Stop()` and the engine teardown only run from the request
handlers: after `disconnect`
([AD7DebugSession.cs L1527](https://github.com/microsoft/MIEngine/blob/fdd455222c3233daf55143b027870639e13f7108/src/OpenDebugAD7/AD7DebugSession.cs#L1527)),
or after a failed launch
([L1477](https://github.com/microsoft/MIEngine/blob/fdd455222c3233daf55143b027870639e13f7108/src/OpenDebugAD7/AD7DebugSession.cs#L1477)).

The process then stays alive because the engine's threads are foreground
threads (`IsBackground` is never set), and .NET does not exit while
foreground threads run:

- the MI transport thread reading gdb's output,
  [StreamTransport.cs L52-L54](https://github.com/microsoft/MIEngine/blob/fdd455222c3233daf55143b027870639e13f7108/src/MICore/Transports/StreamTransport.cs#L52-L54);
- the engine's operation thread,
  [OperationThread.cs L94-L96](https://github.com/microsoft/MIEngine/blob/fdd455222c3233daf55143b027870639e13f7108/src/MIDebugEngine/Engine.Impl/OperationThread.cs#L94-L96).

Because the process never exits, gdb's stdin stays open, so gdb and the
debuggee keep running too.

## Related: `disconnect` without `arguments`

Sending `disconnect` *without* an `arguments` object (which the protocol
allows; `arguments` is optional for this request) has the same outcome: all
three processes keep running. The adapter replies `success: true`, but first
reports this as an `output` event:

```
WARNING: Unable to terminate '/bin/sleep' process. Internal error in OpenDebugAD7. Exception of type 'System.NullReferenceException' was thrown.
   at OpenDebugAD7.AD7DebugSession.HandleDisconnectRequestAsync(IRequestResponder`1 responder)
```

The handler dereferences `responder.Arguments` without a null check
([AD7DebugSession.cs L1495](https://github.com/microsoft/MIEngine/blob/fdd455222c3233daf55143b027870639e13f7108/src/OpenDebugAD7/AD7DebugSession.cs#L1495)):

```csharp
bool shouldDetach = m_isAttach || !responder.Arguments.TerminateDebuggee.GetValueOrDefault(true);
```

Because the exception is caught, the debuggee is never terminated. The
handler then calls `Protocol.Stop()`, yet the process still does not exit,
presumably for the same reason as above. To reproduce, add
`send '{"seq":4,"type":"request","command":"disconnect"}'` after `sleep 5` in
`repro.sh`.

## Impact

VS Code always sends `disconnect`, so this rarely shows up there. It affects
every other DAP client that can end abnormally: a crashing or killed
extension host, command-line and CI tools driving OpenDebugAD7 directly, and
test harnesses whose runner is killed (e.g. by a test timeout that uses
SIGKILL). Each such run leaves three processes behind, one of them a traced
debuggee.

There is also no command-line option or launch setting to change this
behavior.

## Suggested fix

When the protocol reader ends without a `disconnect` having been handled,
perform the same teardown as `disconnect`. That means terminating a launched
debuggee, detaching from an attached one, and shutting the engine down, so
that the process exits. For example, in `Dispatch` after `WaitForReader()`,
or in a handler for the protocol's end of stream.

Marking the transport and operation threads as background threads would also
let the process exit. But it would skip the orderly teardown, and leave the
debuggee to whatever gdb does when its input closes. For a launched debuggee
gdb kills it; I have not checked the attach case.

## Workaround

Clients must send `disconnect`, with an `arguments` object, before exiting.
If they cannot (a crash, or SIGKILL), they must arrange for OpenDebugAD7 to be
killed, for example with
`PR_SET_PDEATHSIG` on Linux. gdb then cleans up the debuggee when its input
closes.
