# Architecture

`cxx-debug-visualize` is a small, dependency-free Python package. It drives a debugger through the
[Debug Adapter Protocol](https://microsoft.github.io/debug-adapter-protocol) (DAP) the way an editor
would, stops at each `visualize(x);` line of a test program, and prints the tree the debugger shows
for `x`. Checking that output is left to the caller.

## Overview

```
cli.py        command line: option deduction and validation, adapter lookup, exit status
  │
runner.py     test run: scan the source, insert and verify breakpoints, visualize at each stop
  │
session.py    debug session: adapter process, launch configuration, DAP request sequence
  │
dap.py        DAP client: message framing, requests, responses and events over stdin/stdout
  │
debug adapter (separate process)
  ├─ OpenDebugAD7 (MIEngine) ── gdb            --adapter miengine  natvis, gdb pretty printers
  ├─ dbgeng-adapter ── DbgEng                  --adapter dbgeng    natvis (Windows)
  ├─ gdb -i dap                                --adapter native    gdb pretty printers
  └─ lldb-dap (lldb-vscode)                    --adapter native    lldb formatters
```

Each layer only uses the one below it. Everything runs on a single thread: waiting for a response
or event means reading messages from the adapter until it arrives.

## Test programs

A test program is ordinary C++ built with debug information. The only requirements are the presence
of lines with `visualize` invocations, and for those invocations to generate executable code where a breakpoint can later be placed.

## Modules

### `cli.py`

Parses the command line using `argparse`. Some options have default values deduced based on other
options. Inconsistent combinations of options are rejected with exit code `2`.

* **Debugger** (`gdb`, `lldb` or `dbgeng`): `--debugger`, otherwise `dbgeng` with the dbgeng
  adapter (`--adapter dbgeng` or `--dbgeng`), otherwise the visualizer decides (`--gdb-printers`
  means `gdb`, `--lldb-formatters` means `lldb`). Natvis is technically debugger-independent, so
  with `--natvis` the type is deduced from the name of `--debugger-path`, defaulting to `gdb`.
  However, Natvis with LLDB has not yet been tested and is for now unsupported.
* **Adapter** (`miengine`, `dbgeng` or `native`): `--adapter`, otherwise `dbgeng` for the `dbgeng`
  debugger, `miengine` for `--natvis` or when `--miengine` is given, and `native` otherwise. Natvis
  requires `miengine` or `dbgeng`, LLDB requires `native`, and the `dbgeng` debugger and adapter
  require each other.
* **OpenDebugAD7** (only required with `--adapter=miengine`): `--miengine`, then
  `$CXX_DEBUG_VISUALIZE_MIENGINE`, then the newest VS Code C/C++ extension found by
  `adapter.find_miengine()`.
* **dbgeng adapter** (only required with `--adapter=dbgeng`): `--dbgeng`, then
  `$CXX_DEBUG_VISUALIZE_DBGENG`. `--miengine` and `--dbgeng` are mutually exclusive.
* All specified paths must be valid. The debugger and adapter (if any) must be executable.

Finally it executes the program using `Runner` and returns 0 on success and 1 otherwise. If the
read end of stdout is closed early, the remaining output is discarded instead of failing noisily.

### `runner.py`

Scans the test source for lines consisting of exactly `visualize(identifier);`. Other lines are
ignored, so a breakpoint never lands on a line containing anything other than the invocation.

`Runner.run()` then:

1. Starts a `DebugSession` with a breakpoint on each of those lines.
2. Checks that every breakpoint is verified and bound to exactly the requested line. A breakpoint
   that moved to another line (e.g. because the call produced no code) is an error rather than a
   silent stop elsewhere.
3. Waits for each stop. At a breakpoint on a `visualize` line it prints a header,
   `visualize(x) at file:line`, evaluates `x` in the `watch` context and prints the result along
   with its direct children, one line each as `name = value [type]`. Children are not expanded
   further. For Natvis, `[More...]` pages are flattened into the list and `[Raw View]` is dropped.
   Any other stop (e.g. a crash) is an error.
4. Ends when the program terminates or exits, and closes the session.

The run fails if `cxx-debug-visualize` finds an error (printed to stderr with an `error:` prefix),
if a request fails, if the adapter reports Natvis diagnostics, or if the adapter writes anything
to its stderr. The adapter's own messages are passed on verbatim.

### `session.py`

`DebugSession` owns one adapter process and knows how each adapter must be driven.

* **Adapter process:** `OpenDebugAD7` (a `.dll` build is run with `dotnet`), the dbgeng adapter,
  `lldb-dap`, or `gdb -i dap`, which is started with the script loaded and the program given up
  front.
* **Launch configuration:** For `OpenDebugAD7`, a `cppdbg` configuration as VS Code would send it,
  with `visualizerFile` and `showDisplayString` for Natvis, or `setupCommands` that enable pretty
  printing and load the script. For LLDB, `initCommands` that load the formatter script. For the
  dbgeng adapter, its own: the program, its arguments and working directory, `visualizerFile`,
  `defaultVisualizers`, and `debuggerPath` for `--debugger-path`.
* **Isolation:** If `default_visualizers` is true, the debuggers's default visualizers are loaded.
  Otherwise, adapter and debugger specific configuration is provided in order to disable all default
  visualizers. This ensures that test results do not depend on the host configuration.
  * GDB: Init files are not read, regardless of configuration (`-nx`).
  * GDB: If disabled, Python script auto-loading is disabled (`set auto-load python-scripts off`).
  * GDB: If enabled, when using Natvis with MIEngine, GDB pretty printing is enabled
    (`enable-pretty-printing`).
  * LLDB: If disabled, the `c++` visualizer category is disabled (`type category disable -l c++`).
  * dbgeng: If disabled, `defaultVisualizers=false` is passed to the adapter on startup.
* **Request order:** `OpenDebugAD7`, the dbgeng adapter and LLDB follow the DAP specification
  (`launch`, then breakpoints on `initialized`, then `configurationDone`). GDB 14 and 15 run the
  program as soon as `launch` arrives, so for GDB the breakpoints are set and configuration is
  finished first, and `launch` comes last (fixed in GDB 16).
* **Breakpoints:** Their state is kept from the `setBreakpoints` reply and updated by `breakpoint`
  events. `OpenDebugAD7`'s initial reply only echoes the requested lines, meaning it is important to
  wait for the subsequent `breakpoint` events to verify breakpoint locations.
* **Diagnostics:** MIEngine reports Natvis problems as `[Natvis]` console output, as does the dbgeng
  adapter when the Natvis file fails to load, which is collected for the runner.

`VisualizationNode` represents one row of the visualization tree: name, value, type and the
reference used to fetch its children.

### `dap.py`

`DapClient` starts the adapter process and speaks DAP over its stdin and stdout
(`Content-Length`-framed JSON). Responses are kept by sequence number and events are queued. An
optional callback may be used to process each event as it arrives, which is how the session tracks
breakpoints. Requests from the adapter to the client (e.g. `runInTerminal`) are declined.

### `adapter.py`

Contains utilities related to debug adapters (e.g. tool discovery from the environment).

## `dbgeng-adapter/`

A DAP server for the Windows debug engine (DbgEng), in C++, built separately with CMake (Windows
only). It supports what `cxx-debug-visualize` uses: one program, reported as a single thread,
line breakpoints, the top stack frame, and values with their direct children.

* `main.cpp` implements the protocol. Requests are handled one at a time, and none are read while
  the program runs.
* `engine.cpp` (`debugger`) drives DbgEng through its COM interfaces. It loads `dbgeng.dll` from
  the Debugging Tools for Windows (or `debuggerPath`), starts the program stopped at the loader's
  initial breakpoint, and loads the Natvis file with `.nvload`, after unloading the ones DbgEng
  loads by default (`.nvunloadall`) if `defaultVisualizers` is false. Expressions are evaluated with
  DbgEng's data model, which applies the Natvis file: values are its display strings, with
  integers in decimal, and children are the visualizer's items and elements, or otherwise the
  fields.

## Self-tests

The unit tests (line scanning, launch configurations, adapter discovery, debugger type deduction)
need nothing but Python. The integration tests run the fixture program under each adapter with good,
bad and malformed visualizers, and check both the printed trees and the errors reported. Like the
example's tests, they disable the default visualizers, so that only the visualizer under test is
active.

`python3 -m tests` takes the fixture program (`--program`) and the executables to test with
(`--gdb`, `--lldb-dap`, `--miengine`, `--dbgeng`). An integration test class runs only when the
executables it needs are given, and is otherwise skipped and left out of `--list`. The self-tests
never compile anything. CMake is used to build the fixture program and CTest to drive the test
execution.

## CMake

### Configuration
* `CXXDEBVIS_GDB`: GDB executable name or absolute path. Enables GDB pretty printer tests.
* `CXXDEBVIS_LLDB_DAP`: LLDB DAP server executable name or absolute path. Enables LLDB formatter
  tests.
* `CXXDEBVIS_MIENGINE`: `OpenDebugAD7` executable name or absolute path. Enables Natvis tests (GDB
  is also required).
* `CXXDEBVIS_DBGENG`: dbgeng adapter executable name or absolute path. Enables Natvis tests with
  DbgEng (Windows).

At least one debugger tool (GDB, LLDB or the dbgeng adapter) must be specified. Only the `Debug`
configuration is supported.
