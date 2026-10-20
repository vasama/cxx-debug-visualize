# cxx-debug-visualize — unit tests for C++ debugger visualizers

`cxx-debug-visualize` prints what a debugger shows for your C++ objects, so a
test can compare it with the expected output and check your visualizers:
`.natvis` files, gdb pretty printers and lldb formatters. It talks to the
debugger through the Debug Adapter Protocol (DAP), as VS Code does, either:

* through the debug adapter of VS Code's C/C++ extension (OpenDebugAD7, the
  `cppdbg` debug type), so a passing test means the object shows up that way
  in VS Code's Variables, Watch and hover views; natvis files are only
  supported this way;
* or through the debugger's own DAP support: `gdb -i dap` (GDB 14 and later)
  or lldb-dap, as used by other editors and VS Code extensions.

```cpp
mylib::Vector<int> v;
for (int i = 1; i <= 3; ++i)
  v.push_back(i * 10);
visualize(v);
```

prints, and the test expects (in `test_containers.natvis.txt`):

```
visualize(v) at test_containers.cpp:34
  { size=3 } [mylib::Vector<int>]
    [size] = 3 [std::size_t]
    [capacity] = 4 [std::size_t]
    [0] = 10 [int]
    [1] = 20 [int]
    [2] = 30 [int]
```

With a typo in the `<ArrayItems><Size>` of `mylib::Vector`'s natvis entry, the
debugger silently drops the whole `<Expand>` and shows the plain members
instead. cxx-debug-visualize itself succeeds, and the comparison reports it:

```
 visualize(v) at test_containers.cpp:34
   { size=3 } [mylib::Vector<int>]
-    [size] = 3 [std::size_t]
-    [capacity] = 4 [std::size_t]
-    [0] = 10 [int]
-    [1] = 20 [int]
-    [2] = 30 [int]
+    Begin = 0x? [int *]
+    Size = 3 [std::size_t]
+    Capacity = 4 [std::size_t]
```

## Installation

```
pipx install cxx-debug-visualize
```

(or `pip install cxx-debug-visualize`) installs the `cxx-debug-visualize`
command. It needs Python 3.10 or later and uses only the standard library.
Running tests also needs, depending on what you test:

* a C++ compiler, to build the test programs with debug information;
* for gdb pretty printers: gdb 14 or later (for its own DAP support), and/or
  gdb with OpenDebugAD7 (see "Getting the debug adapter"), to test them as
  VS Code's C/C++ extension shows them;
* for lldb formatters: lldb-dap (called lldb-vscode before LLVM 18; some
  distributions only install a versioned name such as `lldb-vscode-16`);
* for natvis files: OpenDebugAD7 and gdb.

gdb and lldb-dap are looked up on `PATH`, unless `--debugger-path` names them.

Two optional extras are not part of the package; take them from the
[repository](https://github.com/vasama/cxx-debug-visualize) if you want them:

* [`include/cxx_debug_visualize.h`][header], which defines the `visualize()`
  function tests call (a test can just as well define its own, see "Writing
  tests");
* the CMake helper [`cmake/CxxDebugVisualize.cmake`][cmake], which builds test
  programs and registers CTest tests (see "CMake / CTest").

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
  applies in the Variables pane, Watch and hover. `cxx-debug-visualize` always turns
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
| More than 50 children | paged: children 50 and up sit under a `[More...]` node (cxx-debug-visualize flattens the pages into the list) |
| `Expand` present | a `[Raw View]` child is added, unless `HideRawView="true"` (cxx-debug-visualize leaves it out of its output) |
| `Synthetic`, `CustomListItems` | parsed, but **silently ignored** (no children) |
| `TreeItems` `ValueNode Name="[{Key}]"` | name ignored; children are `[0]`, `[1]`, … |
| `{p,[n]s8}` string length | `[n]` ignored; the whole C string is shown, prefixed by its address |
| Invalid expression in `DisplayString` / `Item` | **no diagnostic**; the text `-var-create: unable to create variable object` appears inside the value |
| Invalid `Condition` | treated as false, silently |
| Invalid `ArrayItems` `<Size>` (etc.) | the **whole `Expand` is dropped silently** and raw members are shown |
| Malformed XML | `[Natvis] [Error] ... while reading file` on the debug console; the file is ignored |

Most mistakes fail silently. That is why natvis files need tests, and why
`cxx-debug-visualize` also looks for the symptoms it can detect itself.

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
  installed ones, e.g. libstdc++'s for `std::` types. `cxx-debug-visualize`
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

## How cxx-debug-visualize works

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
   * cxx-debug-visualize's own errors, prefixed with `error: `, such as an unexpected
     stop (e.g. a segfault), the adapter going away, or a breakpoint that
     landed on a different line than its `visualize` call (see below).
     A breakpoint that is not set on its own line stops the run at once,
     before any further output.

   Evaluation errors and calls that are never reached are not reported
   separately: they show up as output that differs from the expected output.

The test (e.g. the CMake helper below) then compares stdout with the expected
output.

The implementation is pure Python standard library (3.10+): `cxx_debug_visualize/dap.py`
is a small DAP client, and `runner.py` holds the test logic.

## Writing tests

A test is an ordinary C++ program compiled with `-g -O0`. Each line holding
just `visualize(x);` prints the tree of `x` when it runs. A line holding
anything else as well (another statement, even a trailing comment) is not a
breakpoint.

`visualize` only has to exist. The repository's `include/cxx_debug_visualize.h`
defines it as a no-op function, but a test can define its own instead, e.g.:

```cpp
template <typename T> void visualize(const T &) {}
```

Each `visualize` line must compile to code of its own. If it doesn't, e.g.
inside `if (false)` or an `#if 0` block, or when `visualize` is a macro that
expands to nothing or to code-free expressions such as `(void)(x)`, gdb moves
its breakpoint to the next line with code, and cxx-debug-visualize fails with
`breakpoint landed on line N instead` rather than stopping somewhere else. A
function call, as above, always compiles to code at `-O0`.

### Output format

```
visualize(v) at test_containers.cpp:34
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

### Expected output

A test's expected output is a text file holding exactly what cxx-debug-visualize
prints, one per visualizer and debug adapter: the CMake helper below compares
the output of `tests/test_containers.cpp` with
`tests/test_containers.natvis.txt`, `tests/test_containers.gdb.txt` (pretty
printers through OpenDebugAD7), `tests/test_containers.gdb-dap.txt` (pretty
printers through gdb's own DAP support) and `tests/test_containers.lldb-dap.txt`
(lldb formatters through lldb-dap). Before comparing, it replaces every
hexadecimal number (`0x...`) with `0x?`, because addresses differ between
machines; the expected files contain `0x?` in their place:

```
visualize(hello) at test_strings.cpp:13
  0x? "hello" [mylib::String]
    [size] = 5 [std::size_t]
```

* The comparison is exact: every line, value and amount of indentation counts,
  and so does the line number in each header. Adding or removing lines in the
  test source above a call changes its expected output.
* cxx-debug-visualize doesn't flag evaluation errors or unreached calls itself. A failed
  natvis expression shows as `-var-create: unable to create variable object` in
  place of the value, a pretty printer that raises leaves the value empty or
  the children missing, and an unreached call prints nothing; all of these
  change the output.
* Calls in other functions print when that function runs, so their output
  appears in execution order, which may not be source order. See `greet()` in
  [`example/tests/test_strings.cpp`][example-strings].

When a test fails, the helper prints a diff and writes the actual output to
`<kind>.<name>.actual.txt` in the build directory. To create or update an
expected file, check that output and copy it over the expected file.

### Testing several visualizers together

A test source can be checked against a natvis file, a pretty-printer script
and an lldb formatter script for the same types, e.g. when a library ships
all of them; each run has its own expected file. The example's printers
([`example/printers/mylib_printers.py`][example-printers]) and formatters
([`example/formatters/mylib_formatters.py`][example-formatters]) mirror
[`example/natvis/mylib.natvis`][example-natvis]
(same display strings and children, the members of `Point`, `[0]`, `[1]`, ...
for the map), so its expected files are the same except where a debugger
formats a value in its own way: gdb for `Optional<String*>`, and lldb-dap,
which puts a space before summaries and shows a reference's or pointer's
address before the summary of what it points to. See
[`example/tests/`][example-tests] for complete tests.

### Finding out what the debugger shows

Run `cxx-debug-visualize` by hand to see its output, e.g. to write a first expected
file (replace the addresses with `0x?`, e.g. with
`sed -E 's/0x[0-9a-fA-F]+/0x?/g'`), or let a failing test write it.

## Running

```
python3 -m cxx_debug_visualize [--debugger gdb|lldb] [--debugger-path PATH] \
    [--adapter PATH | --vs-code-adapter] \
    (--natvis FILE.natvis | --gdb-printers FILE.py | --lldb-formatters FILE.py) [options] \
    TEST.cpp PROGRAM [--] [ARG...]
```

`TEST.cpp` is the test source: its `visualize(x);` lines get
breakpoints. Calls in other files of the program are not breakpoints.

Without a debug adapter (`--adapter`, `--vs-code-adapter` or
`$CXX_DEBUG_VISUALIZE_ADAPTER`), cxx-debug-visualize uses the debugger's own DAP support,
found on `PATH` unless `--debugger-path` gives its path: `gdb -i dap` (GDB 14 and
later), or lldb-dap (called lldb-vscode before LLVM 18). natvis needs a debug
adapter (OpenDebugAD7).

| Option | Meaning |
|---|---|
| `--debugger gdb\|lldb` | the debugger (default: deduced from `--debugger-path`, otherwise `gdb`); `lldb` can't be used with a debug adapter |
| `--debugger-path PATH` | the debugger to run instead of the one found on `PATH`: the gdb executable, or lldb's DAP server (`lldb-dap`, `lldb-vscode`, e.g. `/usr/bin/lldb-vscode-16`). Without `--debugger`, the type is deduced from the file name: `lldb` in it means lldb, `gdb` means gdb. With OpenDebugAD7, a gdb path is passed as `miDebuggerPath` |
| `--adapter PATH` | OpenDebugAD7 to use; by default, `$CXX_DEBUG_VISUALIZE_ADAPTER` (see below) |
| `--vs-code-adapter` | use the OpenDebugAD7 of the newest installed VS Code C/C++ extension (see below) |
| `--natvis FILE` | the natvis file under test; requires a debug adapter |
| `--gdb-printers FILE` | the gdb pretty-printer script (Python) under test; requires `--debugger gdb` |
| `--lldb-formatters FILE` | the lldb formatter script (Python, loaded with `command script import`) under test; requires `--debugger lldb`. Exactly one of `--natvis`, `--gdb-printers` and `--lldb-formatters` is required |
| `--trace` | dump DAP traffic to stderr |
| `ARG...` | arguments after `PROGRAM` are passed to it; put `--` before them if any starts with `-` |

The output goes to stdout. A test passes if cxx-debug-visualize exits with status 0
and its output matches the expected output (see above). The installed package
provides the same as a `cxx-debug-visualize` command (see "Installation").

There is no timeout: cxx-debug-visualize waits as long as the program runs; stop it
with Ctrl+C. cxx-debug-visualize doesn't handle signals itself. When it exits, the
debug adapter's input closes, and the adapter is expected to shut down, taking
gdb and the program with it. Current OpenDebugAD7 releases don't do this:
they keep running (with gdb and the program) when their input closes. Until
this is fixed in MIEngine, Ctrl+C in a terminal still cleans up (the adapter
receives the SIGINT too),
but killing cxx-debug-visualize alone, e.g. with SIGTERM, leaves those processes
behind.

### CMake / CTest

The CMake helper is not part of the PyPI package: use it from a checkout of
the repository. It runs cxx-debug-visualize from that checkout, so the package
doesn't need to be installed for it.

```cmake
list(APPEND CMAKE_MODULE_PATH path/to/cxx-debug-visualize/cmake)
include(CxxDebugVisualize)
enable_testing()

cxx_debug_visualize_add_test(test_containers
  SOURCES tests/test_containers.cpp
  NATVIS natvis/mylib.natvis                  # at least one of these three
  GDB_PRINTERS printers/mylib_printers.py
  LLDB_FORMATTERS formatters/mylib_formatters.py
  LINK_LIBRARIES mylib)
```

This builds the program once, with `-O0 -g`, and registers CTest tests (label
`visualizers`): `natvis.test_containers` for the natvis file, and for the
pretty printers both `gdb.test_containers` (through OpenDebugAD7, as in VS
Code) and `gdb-dap.test_containers` (through gdb's own DAP support, which needs
GDB 14 or later; `$CXX_DEBUG_VISUALIZE_ADAPTER` is ignored there), and
`lldb-dap.test_containers` for the lldb formatters (through lldb-dap, which
must be on `PATH` when the tests run). Each test runs cxx-debug-visualize and
fails unless it succeeds and its output matches the expected file (see
"Expected output" above). The first file in `SOURCES` is the test source: its
`visualize` lines are breakpoints, and its expected files sit next to it
(`tests/test_containers.natvis.txt`, `tests/test_containers.gdb.txt`,
`tests/test_containers.gdb-dap.txt`, `tests/test_containers.lldb-dap.txt`).
With `NATVIS` or `GDB_PRINTERS`, `CXX_DEBUG_VISUALIZE_ADAPTER` must be set
when configuring; configuration fails without it. See [`example/`][example]
for a complete project, which tests `natvis/mylib.natvis`,
`printers/mylib_printers.py` and `formatters/mylib_formatters.py` against the
same tests:

```
cmake -S example -B build -DCXX_DEBUG_VISUALIZE_ADAPTER=/path/to/OpenDebugAD7
cmake --build build && ctest --test-dir build -L visualizers
```

## Getting the debug adapter

`--adapter` gives the path of an `OpenDebugAD7` executable (or
`OpenDebugAD7.dll`, run with `dotnet`). Without it, `cxx-debug-visualize` uses the
`CXX_DEBUG_VISUALIZE_ADAPTER` environment variable. Without either, and without
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
  MIT-licensed [MIEngine](https://github.com/microsoft/MIEngine) sources
  instead, with the .NET SDK (8 or later):

  ```
  git clone --depth 1 https://github.com/microsoft/MIEngine.git
  sh MIEngine/PublishOpenDebugAD7.sh -c Release -o "$PWD/miengine"
  cxx-debug-visualize --adapter miengine/OpenDebugAD7 ...
  ```

  The build is self-contained: it includes the .NET runtime, so running it
  needs no .NET installation. Give `-o` an absolute path, since the script
  changes to its own directory. The [GitHub Actions workflow][workflow] builds
  it this way, from a pinned MIEngine commit, and caches the result.

  The source-built adapter produced the same results as the one in cpptools
  1.34.4 on the example and self-tests.

## Self-tests

The [self-tests][selftest] are part of the repository, not of the package. The
root `CMakeLists.txt` builds their fixture program and runs them with CTest;
from a checkout:

```
cmake -S . -B build -DCXX_DEBUG_VISUALIZE_ADAPTER=/path/to/OpenDebugAD7
cmake --build build
ctest --test-dir build --output-on-failure
```

CMake builds `selftest/fixtures/prog.cpp` and passes the program to the
self-tests (`python3 -m selftest --program PATH …`), which compile nothing
themselves. The program crashes after its last `visualize()` call when given
an argument, which the crash tests pass to it.

Each self-test is a CTest test of its own, named by its unittest ID, e.g.
`selftest.test_scan.DiscoverTestLinesTests.test_only_whole_line_calls`, so
`ctest -R LldbTests` runs a subset and `ctest -j 8` runs them in parallel.
CMake lists the tests (`python3 -m selftest --list`) when it configures, and a
build re-runs that when a file in `selftest/` changes; each test runs with
`python3 -m selftest --test ID`.

The tests of the `visualize` line scanner and of the launch configurations
always run. The integration tests need the fixture programs, and gdb and
`CXX_DEBUG_VISUALIZE_ADAPTER` (`--adapter`). They check the printed trees for
natvis files and pretty printers (including unexpanded children, nested
flattened `[More...]` pages, the `map` display hint, calls in loops and calls
never reached), how bad visualizers show in them (natvis evaluation errors,
a dropped `Expand`, raising printers), and the errors cxx-debug-visualize
reports (malformed XML, a printer script that doesn't load, crashes). The tests
of gdb's own DAP support check the printed trees and crashes; they need gdb 14
or later, but no adapter. The lldb tests check the same for lldb formatters
([`selftest/fixtures/good_formatters.py`][selftest-formatters]); they need
lldb-dap (or lldb-vscode) on `PATH`.

Tests whose requirements are missing are skipped, and CTest reports them as
skipped. With `-DCXX_DEBUG_VISUALIZE_FAIL_ON_SKIP=ON` (`--fail-on-skip`), a
skipped test fails instead, saying why, so a passing run means every test ran;
the GitHub workflow uses it.

The [GitHub Actions workflow][workflow] runs the self-tests and the example's
CTest tests on every released Python version that is not end-of-life, with
OpenDebugAD7 built from the MIEngine sources, gdb and lldb 18.

## Limitations

* The debugger is the `gdb` or lldb-dap found on `PATH`, or given with
  `--debugger-path`. lldb is only supported through lldb-dap, so not with
  OpenDebugAD7 or natvis.
* Windows' `cppvsdbg` / Visual Studio natvis is a different engine and is not
  tested by this tool.
* Exceptions inside pretty printers pass silently (see above); only the
  comparison with the expected output catches them.

## License

cxx-debug-visualize is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. See [LICENSE.md][license] for the full text.

The exception is [`include/cxx_debug_visualize.h`][header], which test programs
include: it is under the MIT No Attribution License (MIT-0, see
[LICENSE-MIT-0.txt][license-mit-0]), so it can be used, copied and changed
freely, without keeping any notice.

[header]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/include/cxx_debug_visualize.h
[cmake]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/cmake/CxxDebugVisualize.cmake
[example]: https://github.com/vasama/cxx-debug-visualize/tree/HEAD/example
[example-tests]: https://github.com/vasama/cxx-debug-visualize/tree/HEAD/example/tests
[example-strings]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/example/tests/test_strings.cpp
[example-natvis]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/example/natvis/mylib.natvis
[example-printers]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/example/printers/mylib_printers.py
[example-formatters]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/example/formatters/mylib_formatters.py
[selftest]: https://github.com/vasama/cxx-debug-visualize/tree/HEAD/selftest
[selftest-formatters]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/selftest/fixtures/good_formatters.py
[license]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/LICENSE.md
[license-mit-0]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/LICENSE-MIT-0.txt
[workflow]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/.github/workflows/test.yml
