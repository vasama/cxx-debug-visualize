# cxx-vistest — unit tests for natvis files and gdb pretty printers in VS Code

`cxx-vistest` prints what VS Code's debugger shows for your C++ objects, so
[FileCheck](https://llvm.org/docs/CommandGuide/FileCheck.html) can check your
visualizers: `.natvis` files, or gdb pretty printers written in Python. It uses
the same debug adapter that VS Code's C/C++ extension uses (`cppdbg`), so a
passing test means the object shows up that way in VS Code's Variables, Watch
and hover views.

```cpp
int main() {
  mylib::Vector<int> v;
  for (int i = 1; i <= 3; ++i)
    v.push_back(i * 10);
  visualize(v);
  // CHECK: visualize(v) at test_vector.cpp:[[@LINE-1]]
  // CHECK-NEXT:   { size=3 } [mylib::Vector<int>]
  // CHECK-NEXT:     [size] = 3 [std::size_t]
  // CHECK-NEXT:     [capacity] = 4 [std::size_t]
}
```

With a typo in the `<ArrayItems><Size>` of `mylib::Vector`'s natvis entry, the
debugger silently drops the whole `<Expand>`, and FileCheck reports it:

```
$ cxx-vistest --adapter $ADAPTER --natvis mylib.natvis test_vector.cpp ./test_vector \
    | FileCheck --dump-input=never test_vector.cpp
test_vector.cpp:11:17: error: CHECK-NEXT: expected string not found in input
 // CHECK-NEXT: [size] = 3 [std::size_t]
                ^
<stdin>:2:33: note: scanning from here
 { size=3 } [mylib::Vector<int>]
                                ^
<stdin>:4:2: note: possible intended match here
 Size = 3 [std::size_t]
 ^
```

## How natvis support works in VS Code

These findings come from reading and running cpptools 1.34.4 and MIEngine `main` (September 2026).

* A `cppdbg` launch configuration starts **OpenDebugAD7**, which the C/C++
  extension ships in `debugAdapters/bin/`. VS Code talks to it with the
  Debug Adapter Protocol (DAP). OpenDebugAD7 wraps **MIEngine**
  ([microsoft/MIEngine](https://github.com/microsoft/MIEngine), MIT
  licensed). MIEngine drives gdb (or lldb-mi) through the GDB/MI protocol.
* **Natvis is implemented entirely inside MIEngine**
  (`src/MIDebugEngine/Natvis.Impl/Natvis.cs`), not in gdb or VS Code. MIEngine
  loads the files named by `visualizerFile` (a string or an array) and
  matches types by name, including `*` wildcards. It rewrites each `{expr}`
  and `<Item>` into an expression and asks gdb to evaluate it
  (`-var-create`). **Natvis expressions are therefore evaluated by gdb's C++
  parser, not MSVC's expression evaluator.**
* On Windows, the `cppvsdbg` type uses Visual Studio's closed-source debugger
  engine instead. That is a different natvis implementation, and this tool
  does not cover it.
* `showDisplayString` defaults to `false` in VS Code. With it off, a
  visualized object shows as `{...}` with its plain members as children; if
  its type has an `<Expand>`, the visualization sits one level down, in a
  `[Visualized View]` child (where display strings are shown). Types with only
  a `DisplayString` show no visualization at the top level at all. The same
  applies in the Variables pane, Watch and hover. `cxx-vistest` always turns
  the setting on, so tests see the visualization directly. Tell users of your
  natvis file to set `"showDisplayString": true`.
* `visualizerFile` is documented as not compatible with gdb pretty printers,
  so don't enable pretty printing in `setupCommands`.

### Behaviours the tests have to deal with

Found by probing cpptools 1.34.4 with gdb 15 and confirmed in the MIEngine source:

| Natvis construct | Behaviour in VS Code (`cppdbg`) |
|---|---|
| `DisplayString`, `Condition`, format specifiers `,x` `,b` `,o` | work |
| `,s8` on `char*` / `,na` | the address is still shown before the string (`0x5555… "text"`) |
| `Item`, `ArrayItems`, `IndexListItems`, `LinkedListItems`, `TreeItems`, `ExpandedItem`, `Intrinsic` | work |
| More than 50 children | paged: children 50 and up sit under a `[More...]` node (cxx-vistest flattens the pages into the list) |
| `Expand` present | a `[Raw View]` child is added, unless `HideRawView="true"` (cxx-vistest leaves it out of its output) |
| `Synthetic`, `CustomListItems` | parsed, but **silently ignored** (no children) |
| `TreeItems` `ValueNode Name="[{Key}]"` | name ignored; children are `[0]`, `[1]`, … |
| `{p,[n]s8}` string length | `[n]` ignored; the whole C string is shown, prefixed by its address |
| Invalid expression in `DisplayString` / `Item` | **no diagnostic**; the text `-var-create: unable to create variable object` appears inside the value |
| Invalid `Condition` | treated as false, silently |
| Invalid `ArrayItems` `<Size>` (etc.) | the **whole `Expand` is dropped silently** and raw members are shown |
| Malformed XML | `[Natvis] [Error] ... while reading file` on the debug console; the file is ignored |

Most mistakes fail silently. That is why natvis files need tests, and why
`cxx-vistest` also looks for the symptoms it can detect itself.

## How gdb pretty printers work in VS Code

Found by running cpptools 1.34.4 with gdb 15:

* gdb's own [pretty printers](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Pretty-Printing.html)
  (Python classes with `to_string()`, `children()` and `display_hint()`) are
  applied by gdb itself; MIEngine shows what gdb's `-var-create` and
  `-var-list-children` return. They are enabled through `setupCommands`:
  `-enable-pretty-printing`, plus a command that loads the printers (e.g.
  `source printers.py`), or gdb's auto-loading. Without
  `-enable-pretty-printing`, gdb ignores printers and shows plain members.
* They don't mix with natvis (`visualizerFile` is documented as not
  compatible with them), so a launch uses one or the other.
* gdb also loads printers from its init files (`~/.gdbinit`) and auto-loads
  installed ones, e.g. libstdc++'s for `std::` types. `cxx-vistest`
  switches both off (`-nx`, `set auto-load python-scripts off`), so only the
  printers under test are active, and results don't depend on the machine.

| Printer feature | Behaviour in VS Code (`cppdbg`) |
|---|---|
| `to_string()` | the value; a lazy string with the `"string"` display hint is shown quoted |
| `to_string()` returning `None` | MIEngine shows a summary of the children, e.g. `{[value] = 42}` |
| `children()` | the children, with the names the printer yields; no `[Raw View]` |
| no `children()` | no children at all (not the plain members) |
| `display_hint()` `"map"` | pairs of children become one child each, named by the key (`[10] = 100`) |
| many children | all listed at once; no `[More...]` paging |
| a pointer to a printed type | the pointer is shown as an address (unlike natvis), unless a lookup function also handles the pointer type, as the example's printers do for `mylib::String *` |
| exception in `to_string()` / `children()` | **no diagnostic**; the value is empty, or the children are missing |
| error while loading the script (e.g. a syntax error) | the launch fails: `Unable to start debugging. ... Error occurred in Python: ...` |

## How cxx-vistest works

1. It scans the test source for lines that consist of exactly
   `visualize(identifier);`, and sets a breakpoint on each.
2. It starts OpenDebugAD7, sends `initialize`, then `launch` with a `cppdbg`
   configuration like VS Code's, sets the breakpoints and runs the program.
   The visualizer under test is either a natvis file (`visualizerFile`,
   `showDisplayString`) or a pretty-printer script (`setupCommands` that
   enable pretty printing and `source` the script, isolated as described
   above).
3. **Every time** a breakpoint is hit, it evaluates the identifier with the DAP
   `evaluate` request (context `watch`, as in the Watch window), walks the tree
   with `variables`, and prints it to stdout. A call in a loop prints once per
   iteration.
4. It reports problems the output alone may not show on stderr, and exits
   with status 1 if there are any:
   * errors the debug adapter reports, printed verbatim: failed requests
     (e.g. a failed launch), breakpoints it could not set, and its natvis
     diagnostics (debug-console lines starting with `[Natvis]`, e.g. for
     malformed XML; warnings too), and anything the adapter writes to its own
     stderr apart from its `waiting for v8 protocol on stdin/stdout` banner
     (e.g. a crash report), shown at the end;
   * cxx-vistest's own errors, prefixed with `error: `, such as an unexpected
     stop (e.g. a segfault), the adapter going away, or a breakpoint that
     landed on a different line than its `visualize` call (see below).
     A breakpoint that is not set on its own line stops the run at once,
     before any further output.

   Evaluation errors and calls that are never reached are not reported
   separately: they show up as output that differs from the CHECK lines.

FileCheck then compares stdout with the `CHECK` lines in the test source.

The implementation is pure Python standard library (3.10+): `cxx_vistest/dap.py`
is a small DAP client, and `runner.py` holds the test logic.

## Writing tests

A test is an ordinary C++ program compiled with `-g -O0`.
`include/cxx_vistest.h` provides `visualize(object)`, a no-op call that
keeps its argument alive. Each line holding just `visualize(x);` prints
the tree of `x` when it runs. A line holding anything else as well (another
statement, even a trailing comment) is not a breakpoint.

Each `visualize` line must compile to code of its own. If it doesn't,
e.g. inside `if (false)` or an `#if 0` block, gdb moves its breakpoint to the
next line with code, and cxx-vistest fails with `breakpoint landed on line N
instead` rather than stopping somewhere else.

### Output format

```
visualize(v) at test_containers.cpp:39
  { size=3 } [mylib::Vector<int>]
    [size] = 3 [std::size_t]
    [capacity] = 4 [std::size_t]
    [0] = 10 [int]
    [1] = 20 [int]
    [2] = 30 [int]
```

* A header line gives the identifier and the call's file name and line.
* Everything below the header is indented by at least one level (two
  spaces). The first such line is the object itself, as `value [type]`,
  without a name.
* Each child is `name = value [type]`, indented one more level. Nodes
  without a type (e.g. a natvis `<Item>` whose expression failed) have no
  `[type]`.
* Below the object come its children: the items its type's visualizer
  produces (with natvis, its members if the type has no `<Expand>`; with a
  pretty printer, what `children()` yields). They are not expanded further,
  since their own children come from their own types' visualizers.
* natvis's `[More...]` pages, which hold children 50 and up of a list, are
  flattened: their children are printed in place, at the list's level, and
  the `[More...]` lines are left out, so the output looks as if the list were
  not paged (as with a pretty printer).
* natvis's `[Raw View]` child, which holds the object's plain members, is left
  out. When a visualizer's `<Expand>` is silently dropped, the plain members
  appear in place of the visualized children.
* Values are printed exactly as the debugger shows them, including addresses.

### Writing CHECK lines

Put the CHECK lines right after the call and pin the header to it with
`[[@LINE-1]]` (FileCheck doesn't allow `@LINE` in `CHECK-LABEL`, so use
`CHECK`):

```cpp
visualize(hello);
// CHECK: visualize(hello) at test_strings.cpp:[[@LINE-1]]
// CHECK-NEXT:   {{0x[0-9a-f]+}} "hello" [mylib::String]
// CHECK-NEXT:     [size] = 5 [std::size_t]
```

* Use `CHECK-NEXT` to fix the structure, and plain `CHECK` to skip lines, such
  as the elements of a long array.
* Match addresses with a regex: `{{0x[0-9a-f]+}}`.
* cxx-vistest doesn't flag evaluation errors or unreached calls itself. A failed
  natvis expression shows as `-var-create: unable to create variable object` in
  place of the value, a pretty printer that raises leaves the value empty or
  the children missing, and an unreached call prints nothing, so give every
  call CHECK lines that pin the values you care about. Avoid patterns such as
  `{{.*}}` on values, which would also match the error text.
* FileCheck ignores differences in amounts of whitespace, so indentation is
  not checked exactly; `CHECK-NEXT` chains still pin the order of the lines.
* Calls in other functions print when that function runs, so their CHECK
  lines go in execution order, which may not be source order. See `greet()` in
  `example/tests/test_strings.cpp`.

### Testing natvis and pretty printers together

A test source can be checked against both a natvis file and a pretty-printer
script for the same types, e.g. when a library ships both. `CHECK` lines then
apply to both runs, and lines where the outputs differ use the prefixes
`NATVIS` and `GDB`, with FileCheck run as `FileCheck --allow-unused-prefixes
--check-prefixes=CHECK,NATVIS` and `... --check-prefixes=CHECK,GDB` (the CMake
helper does this):

```cpp
visualize(ptr);
// CHECK: visualize(ptr) at test_strings.cpp:[[@LINE-1]]
// NATVIS-NEXT:   {{0x[0-9a-f]+}} "hello" [mylib::Optional<mylib::String*>]
// GDB-NEXT:      "hello" = {[size] = 5} [mylib::Optional<mylib::String*>]
// CHECK-NEXT:      [value] = {{0x[0-9a-f]+}} "hello" [mylib::String *]
```

FileCheck reads the lines of all given prefixes as one sequence and ignores
the others, so `-NEXT` lines chain across prefixes. `--allow-unused-prefixes`
lets a test use only one of the prefixes, or neither, when the outputs don't
differ; the flip side is that a misspelt prefix goes unnoticed.

The less the two outputs differ, the more `CHECK` lines the runs share. The
example's printers (`example/printers/mylib_printers.py`) mirror
`example/natvis/mylib.natvis` (same display strings and children, the members
of `Point`, `[0]`, `[1]`, ... for the map), so its tests need a `NATVIS`/`GDB`
pair only where gdb formats a value in its own way. See `example/tests/` for
complete tests.

### Finding out what the debugger shows

Run `cxx-vistest` without piping into FileCheck to see the output to write
CHECK lines against.

## Running

```
python3 -m cxx_vistest [--debugger gdb|lldb] [--adapter PATH | --vs-code-adapter] \
    (--natvis FILE.natvis | --gdb-printers FILE.py | --lldb-formatters FILE.py) [options] \
    TEST.cpp PROGRAM | FileCheck TEST.cpp
```

`TEST.cpp` is the test source: its `visualize(x);` lines get
breakpoints. Calls in other files of the program are not breakpoints.

Without a debug adapter (`--adapter`, `--vs-code-adapter` or
`$CXX_VISTEST_ADAPTER`), cxx-vistest uses the debugger's own DAP support,
found on `PATH`: `gdb -i dap` (GDB 14 and later), or lldb-dap (called
lldb-vscode before LLVM 18). natvis needs a debug adapter (OpenDebugAD7).

| Option | Meaning |
|---|---|
| `--debugger gdb\|lldb` | the debugger (default: `gdb`); `lldb` can't be used with a debug adapter |
| `--adapter PATH` | OpenDebugAD7 to use; by default, `$CXX_VISTEST_ADAPTER` (see below) |
| `--vs-code-adapter` | use the OpenDebugAD7 of the newest installed VS Code C/C++ extension (see below) |
| `--natvis FILE` | the natvis file under test; requires a debug adapter |
| `--gdb-printers FILE` | the gdb pretty-printer script (Python) under test; requires `--debugger gdb` |
| `--lldb-formatters FILE` | the lldb formatter script (Python, loaded with `command script import`) under test; requires `--debugger lldb`. Exactly one of `--natvis`, `--gdb-printers` and `--lldb-formatters` is required |
| `--trace` | dump DAP traffic to stderr |

Use `set -o pipefail` (or check both exit codes) when piping by hand, so an
error from cxx-vistest isn't hidden by a passing FileCheck. `pip install .`
installs a `cxx-vistest` command.

There is no timeout: cxx-vistest waits as long as the program runs; stop it
with Ctrl+C. cxx-vistest doesn't handle signals itself. When it exits, the
debug adapter's input closes, and the adapter is expected to shut down, taking
gdb and the program with it. Current OpenDebugAD7 releases don't do this:
they keep running (with gdb and the program) when their input closes. Until
this is fixed in MIEngine, Ctrl+C in a terminal still cleans up (the adapter
receives the SIGINT too),
but killing cxx-vistest alone, e.g. with SIGTERM, leaves those processes
behind.

### CMake / CTest

```cmake
list(APPEND CMAKE_MODULE_PATH path/to/cxx-vistest/cmake)
include(CxxVistest)
enable_testing()

cxx_vistest_add_test(test_containers
  SOURCES tests/test_containers.cpp
  NATVIS natvis/mylib.natvis                  # at least one of NATVIS and GDB_PRINTERS
  GDB_PRINTERS printers/mylib_printers.py
  LINK_LIBRARIES mylib)
```

This builds the program once, with `-O0 -g`, and registers a CTest test per
visualizer: `natvis.test_containers` and `gdb.test_containers` (label
`visualizers`). Each test pipes cxx-vistest's output into FileCheck and
fails unless both succeed. The first file in `SOURCES` is the test source: its
`visualize` lines are breakpoints and it holds the CHECK lines. With
both visualizers, FileCheck runs with the `NATVIS` and `GDB` prefixes described
above; with one, it uses only `CHECK`. Both tools' paths must be set when
configuring; configuration fails without them. See `example/` for a complete
project, which tests `natvis/mylib.natvis` and `printers/mylib_printers.py`
against the same tests:

```
cmake -S example -B build \
    -DCXX_VISTEST_ADAPTER=/path/to/OpenDebugAD7 \
    -DCXX_VISTEST_FILECHECK=/usr/lib/llvm-18/bin/FileCheck
cmake --build build && ctest --test-dir build -L visualizers
```

## Getting the debug adapter

`--adapter` gives the path of an `OpenDebugAD7` executable (or
`OpenDebugAD7.dll`, run with `dotnet`). Without it, `cxx-vistest` uses the
`CXX_VISTEST_ADAPTER` environment variable. Without either, and without
`--vs-code-adapter`, the debugger's own DAP support is used (see above).

`--vs-code-adapter` uses the adapter of the newest VS Code C/C++ extension
installed in your home directory:
`~/.vscode`, `~/.vscode-insiders`, and `~/.vscode-server` or
`~/.vscode-server-insiders` for remote development (e.g. Remote SSH), each
under `extensions/ms-vscode.cpptools-<version>-<platform>/debugAdapters/bin/`.
The extension makes the adapter executable only when VS Code first activates
it, so a version that has not been activated yet (e.g. right after an update)
is skipped. `--trace` shows which adapter is used.

* **Developer machines**: rely on the installed C/C++ extension
  (`--vs-code-adapter`). You then test exactly the version you debug with.
* **CI**: the extension's license only covers use with Microsoft
  products (VS Code, Visual Studio, …). Build OpenDebugAD7 from the
  MIT-licensed MIEngine sources instead:

  ```
  scripts/build-miengine.sh .miengine        # needs git and the .NET 8 SDK
  cxx-vistest --adapter .miengine/OpenDebugAD7 ...   # needs the .NET 8 runtime
  ```

  The source-built adapter produced the same results as the one in cpptools
  1.34.4 on the example and self-tests.

## Self-tests

```
python3 -m selftest --adapter /path/to/OpenDebugAD7
```

The tests of the `visualize` line scanner and of the launch
configurations always run. The integration tests need `--adapter`, gdb and
g++/clang++, and are skipped otherwise. They check the printed trees for
natvis files and pretty printers (including unexpanded children, nested
flattened `[More...]` pages, the `map` display hint, calls in loops and calls never
reached), how broken visualizers show in them (natvis evaluation errors, a
dropped `Expand`, raising printers), and the errors cxx-vistest reports
(malformed XML, a printer script that doesn't load, crashes). The
tests of gdb's own DAP support check the printed trees and crashes; they need
gdb 14 or later and g++/clang++, but no `--adapter`.

## Limitations

* The debugger is the `gdb` or lldb-dap found on `PATH`. lldb is only supported
  through lldb-dap, so not with OpenDebugAD7 or natvis.
* Windows' `cppvsdbg` / Visual Studio natvis is a different engine and is not
  tested by this tool.
* Exceptions inside pretty printers pass silently (see above); only the CHECK
  lines catch them.

## License

cxx-vistest is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. See [LICENSE.md](LICENSE.md) for the full text.
