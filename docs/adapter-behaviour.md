# Adapter behaviour

Quirks of the debug adapters `cxx-debug-visualize` drives, as observed while building and testing
it, and what they mean for tests. Most of them explain why the expected output of the same test
differs between adapters, or why a broken visualizer only shows up in the output.

Observed with OpenDebugAD7 from vscode-cpptools 1.34.4 and from MIEngine `main` at `fdd4552`
(September 2026), GDB 15, lldb-vscode 16 (lldb-dap 18 in CI) and `lldb-mi` (see below). Other
versions may differ.

## OpenDebugAD7 (MIEngine)

OpenDebugAD7 is the DAP frontend of MIEngine, the debug engine behind the `cppdbg` debug type of VS
Code's C/C++ extension, which Visual Studio also uses to debug with GDB. MIEngine drives GDB through
the GDB/MI protocol.

### General

* Natvis is implemented by MIEngine. MIEngine rewrites each `{expr}` and `<Item>` into an expression
  and requests GDB to evaluate it (`-var-create`), so Natvis expressions are evaluated by GDB's C++
  parser, not by MSVC's expression evaluator. Thus, any MSVC-only syntax is not accepted.
* `showDisplayString` defaults to `false` in VS Code (and in OpenDebugAD7). Testing the Natvis
  display strings as well is obviously desirable, and so `cxx-debug-visualize` turns it back on.
* Natvis diagnostics (e.g. malformed XML) only appear as `[Natvis] ...` debug console output.
  Invalid Natvis files are otherwise ignored by the adapter.
* `setBreakpoints` replies only echo the requested lines. Where a breakpoint was actually placed
  (e.g. because no executable code corresponds to the requested line) is only reported later via
  `breakpoint` events. `cxx-debug-visualize` ignores lines from the original reply and instead waits
  for the relevant events.
* OpenDebugAD7 writes `waiting for v8 protocol on stdin/stdout` to stderr on startup. This output is
  filtered out by `cxx-debug-visualize`.
* OpenDebugAD7 does not exit when its input stream is closed during a session without a `disconnect`
  request. A client that is killed (e.g. by a CI timeout sending SIGTERM) therefore leaves behind a
  ghost debug adapter process. This also means that the debugger and debuggee never get terminated
  either. Ctrl+C in a terminal still cleans up, since the adapter receives the SIGINT too.
* The C/C++ extension only makes OpenDebugAD7 executable when VS Code first activates it, so just
  installing the extension is not sufficient for using it. `cxx-debug-visualize` does not change
  permissions of the executable in order to use it.

### Natvis

| Natvis construct | Behaviour |
|---|---|
| `DisplayString`, `Condition`, format specifiers `,x` `,b` `,o` | works as expected |
| `Item`, `ArrayItems`, `IndexListItems`, `LinkedListItems`, `TreeItems`, `ExpandedItem`, `Intrinsic` | works as expected |
| `,s8` on `char*` / `,na` | the address is still shown before the string (`0x5555… "text"`) |
| `{p,[n]s8}` string length | `[n]` is ignored; the whole C string is shown, prefixed by its address |
| more than 50 children | paged: children 50 and up sit under a `[More...]` node |
| `Expand` present | a `[Raw View]` child is added, unless `HideRawView="true"` |
| `TreeItems` `ValueNode Name="[{Key}]"` | the name is ignored; children are `[0]`, `[1]`, … |
| `Synthetic`, `CustomListItems` | parsed, but **silently ignored** (no children) |
| invalid expression in `DisplayString` / `Item` | **no diagnostic**; `-var-create: unable to create variable object` appears in the value |
| invalid `Condition` | silently treated as false |
| invalid `ArrayItems` `<Size>` (etc.) | the **whole `Expand` is silently dropped** and the raw members are shown |
| malformed XML | `[Natvis] [Error] ... while reading file` on the debug console; the file is ignored |

Most mistakes fail silently, and only show as a difference in the output. (`cxx-debug-visualize`
flattens `[More...]` pages into the list and leaves `[Raw View]` out of its output.)

### GDB pretty printers

Pretty printers are applied by gdb itself; MIEngine shows what gdb's `-var-create` and
`-var-list-children` return. They must be enabled with `-enable-pretty-printing` in
`setupCommands`; without it, gdb ignores printers and shows plain members.

| Printer feature | Behaviour |
|---|---|
| `to_string()` | the value; a lazy string with the `"string"` display hint is shown quoted |
| `to_string()` returning `None` | a summary of the children, e.g. `{[value] = 42}` |
| `children()` | the children, with the names the printer yields; no `[Raw View]` |
| no `children()` | no children at all (not the plain members) |
| `display_hint()` `"map"` | pairs of children become one child each, named by the key (`[10] = 100`) |
| many children | all listed at once; no `[More...]` paging |
| a pointer to a printed type | shown as an address (unlike natvis), unless a lookup function also handles the pointer type |
| exception in `to_string()` / `children()` | **no diagnostic**; the value is empty, or the children are missing |
| error while loading the script (e.g. a syntax error) | the launch fails: `Unable to start debugging. ... Error occurred in Python: ...` |

### LLDB (`lldb-mi`)

With `MIMode: lldb`, MIEngine runs `lldb-mi`, LLDB's implementation of gdb's machine interface,
instead of gdb. The C/C++ extension ships it only for macOS; LLVM no longer does, so elsewhere it is
built from `lldb-tools/lldb-mi`. Observed with `lldb-mi` at `1aa9e8f` (April 2026) and LLDB 18.

* **Natvis shows the same as with gdb**, but for LLDB's spelling of types (`mylib::string *` for
  gdb's `mylib::string*`). Natvis expressions are evaluated by LLDB.
* **An invalid expression shows LLDB's whole error in place of the value**, over several lines (e.g.
  `<1,error: <user expression 1>:1:1: use of undeclared identifier 'no_such_member'`, then the
  source excerpt), where gdb shows `-var-create: unable to create variable object`.
* **lldb formatters show as through `lldb-dap`.** Summaries and synthetic children apply, as LLDB
  computes the values MIEngine shows. But a summary that raises falls back to `{...}`, not to
  lldb's default summary, and a script that fails to import passes silently.
* **Isolation.** `lldb-mi` reads no init files, and LLDB's commands, such as those that load the
  script under test, are `setupCommands`.
* **`lldb-mi` needs `lldb-server`** to run the program. Ubuntu's LLDB looks for it (as
  `lldb-server-18.1.3`, with its version) next to the program using LLDB, where a self-built
  `lldb-mi` does not have it, unless `LLDB_DEBUGSERVER_PATH` names it. Otherwise the launch fails
  with `Unable to start debugging. ... unable to locate lldb-server-18.1.3`.

## GDB (`gdb -i dap`)

GDB has its own DAP support since GDB 14.

* **Request order.** GDB 14 and 15 send `initialized` right after `initialize`, and run the program
  as soon as `launch` arrives, after which `configurationDone` fails with `notStopped`. A client
  must therefore set breakpoints and send `configurationDone` before `launch`, unlike with other
  adapters. GDB 16 follows the DAP specification: `launch` only takes effect after
  `configurationDone`.
* **`setBreakpoints` replies report the real lines** the breakpoints were bound to.
* **The same printer shows differently than through OpenDebugAD7.**
  * With the `"map"` display hint, keys and values are separate children (`key0 = 3`,
    `value0 = 4`, …) instead of one child per pair named by the key.
  * Types are spelled as gdb prints them, e.g. `mylib::string *` rather than `mylib::string*`
    inside template arguments.
  * A `to_string()` returning a value that has its own printer (e.g. a pointer) shows that value
    as gdb formats it, not MIEngine's summary.
* **A printer that raises fails the evaluation** with gdb's message (e.g. `There is no member named
  c.`), which stops the run there, unlike through OpenDebugAD7, where it passes silently.
* **A script that fails to load passes silently**: values show without printers, and only the
  output reveals it. Through OpenDebugAD7 the launch fails instead.
* **Isolation.** gdb reads `~/.gdbinit` and auto-loads installed printers (e.g. libstdc++'s for
  `std::` types) unless told otherwise. `cxx-debug-visualize` always passes `-nx`, and with
  `--no-default-visualizers` also turns off `auto-load python-scripts`, so that only the printers
  under test are active.

## LLDB (`lldb-dap`)

LLDB's DAP server is called `lldb-dap` since LLVM 18, and `lldb-vscode` before that. Some
distributions only install a versioned name, such as `lldb-dap-18` or `lldb-vscode-16`.

* **Until LLVM 18, a summary follows the value, separated by a space.** For types without a value of
  their own (structs, classes), the displayed value is an empty value, a space, and the summary, so
  it starts with a space (e.g. ` (3, -4)`).
* **A reference's or pointer's address is shown before the summary** of what it points to (e.g.
  `0x… 0x… "world"` for a reference to a string whose summary itself starts with an address).
* **A summary does not hide the members.** Unless a synthetic children provider replaces them, the
  plain members are still listed as children.
* **No paging**: all children are listed at once.
* **Formatter errors pass silently.** A summary function that raises falls back to lldb's default
  summary (e.g. `pair @ 0x…`), and a synthetic children provider that raises leaves the children
  missing. A script that fails to import is only reported on the debug console, and values show
  without formatters. Only the output reveals either.
* **Isolation.** lldb's built-in C++ formatters (e.g. for libstdc++ and libc++) are active by
  default. With `--no-default-visualizers`, `cxx-debug-visualize` disables the `c++` category
  before importing the script under test.
* **Output differs between LLVM versions**, so expected output recorded with one version may not
  match another.
