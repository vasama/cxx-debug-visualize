# natvistest — unit tests for natvis files in VS Code

`natvistest` prints what VS Code's debugger shows for your C++ objects, so
[FileCheck](https://llvm.org/docs/CommandGuide/FileCheck.html) can check your
`.natvis` visualizers. It uses the same debug adapter that VS Code's C/C++
extension uses (`cppdbg`), so a passing test means the object shows up that
way in VS Code's Variables, Watch and hover views.

```cpp
int main() {
  mylib::Vector<int> v;
  for (int i = 1; i <= 3; ++i)
    v.push_back(i * 10);
  check_visualizer(v);
  // CHECK: check_visualizer(v) at test_vector.cpp:[[@LINE-1]]
  // CHECK-NEXT:   { size=3 } [mylib::Vector<int>]
  // CHECK-NEXT:     [size] = 3 [std::size_t]
  // CHECK-NEXT:     [capacity] = 4 [std::size_t]
}
```

With a typo in the `<ArrayItems><Size>` of `mylib::Vector`'s natvis entry, the
debugger silently drops the whole `<Expand>`, and FileCheck reports it:

```
$ natvistest run --adapter $ADAPTER --natvis mylib.natvis test_vector.cpp ./test_vector \
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
  applies in the Variables pane, Watch and hover. `natvistest` always turns
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
| More than 50 children | paged: children 50 and up sit under a `[More...]` node |
| `Expand` present | a `[Raw View]` child is added, unless `HideRawView="true"` |
| `Synthetic`, `CustomListItems` | parsed, but **silently ignored** (no children) |
| `TreeItems` `ValueNode Name="[{Key}]"` | name ignored; children are `[0]`, `[1]`, … |
| `{p,[n]s8}` string length | `[n]` ignored; the whole C string is shown, prefixed by its address |
| Invalid expression in `DisplayString` / `Item` | **no diagnostic**; the text `-var-create: unable to create variable object` appears inside the value |
| Invalid `Condition` | treated as false, silently |
| Invalid `ArrayItems` `<Size>` (etc.) | the **whole `Expand` is dropped silently** and raw members are shown |
| Malformed XML | `[Natvis] [Error] ... while reading file` on the debug console; the file is ignored |

Most mistakes fail silently. That is why natvis files need tests, and why
`natvistest` also looks for the symptoms it can detect itself.

## How natvistest works

1. It scans the test source for lines that consist of exactly
   `check_visualizer(identifier);`, and sets a breakpoint on each.
2. It starts OpenDebugAD7, sends `initialize`, then `launch` with a `cppdbg`
   configuration like VS Code's (`visualizerFile`, `showDisplayString`,
   `MIMode`, …), sets the breakpoints and runs the program.
3. **Every time** a breakpoint is hit, it evaluates the identifier with the DAP
   `evaluate` request (context `watch`, as in the Watch window), walks the tree
   with `variables`, and prints it to stdout. A call in a loop prints once per
   iteration.
4. It reports problems the output alone may not show on stderr, and exits
   with status 1 if there are any:
   * errors the debug adapter reports, printed verbatim: failed requests
     (e.g. a failed launch), breakpoints it could not set, and its natvis
     diagnostics (debug-console lines starting with `[Natvis]`, e.g. for
     malformed XML; warnings too);
   * natvistest's own errors, prefixed with `error: `, such as an unexpected
     stop (e.g. a segfault), the adapter going away, or a breakpoint that
     landed on a different line than its `check_visualizer` call (see below).
     A breakpoint that is not set on its own line stops the run at once,
     before any further output.

   Evaluation errors and calls that are never reached are not reported
   separately: they show up as output that differs from the CHECK lines.

FileCheck then compares stdout with the `CHECK` lines in the test source.

The implementation is pure Python standard library (3.8+): `natvistest/dap.py`
is a small DAP client, and `runner.py` holds the test logic.

## Writing tests

A test is an ordinary C++ program compiled with `-g -O0`.
`include/natvistest.h` provides `check_visualizer(object)`, a no-op call that
keeps its argument alive. Each line holding just `check_visualizer(x);` prints
the tree of `x` when it runs. A line holding anything else as well (another
statement, even a trailing comment) is not a breakpoint.

Each `check_visualizer` line must compile to code of its own. If it doesn't,
e.g. inside `if (false)` or an `#if 0` block, gdb moves its breakpoint to the
next line with code, and natvistest fails with `breakpoint landed on line N
instead` rather than stopping somewhere else.

### Output format

```
check_visualizer(v) at test_containers.cpp:39
  { size=3 } [mylib::Vector<int>]
    [size] = 3 [std::size_t]
    [capacity] = 4 [std::size_t]
    [0] = 10 [int]
    [1] = 20 [int]
    [2] = 30 [int]
    [Raw View] = {...}
```

* A header line gives the identifier and the call's file name and line.
* Everything below the header is indented by at least one level (two
  spaces). The first such line is the object itself, as `value [type]`,
  without a name.
* Each child is `name = value [type]`, indented one more level. Nodes
  without a type, such as `[Raw View]`, have no `[type]`.
* Below the object come its children: the items its type's visualizer
  produces (or its members, if the type has no `<Expand>`). They are not
  expanded further, since their own children come from their own types'
  visualizers. The one exception is `[More...]`, which holds children 50 and
  up of the same list; it is followed to the end, each nested page indented
  one more level.
* `[Raw View]` is listed but not expanded. When a visualizer's `<Expand>` is
  silently dropped, `[Raw View]` disappears and the plain members appear
  instead.
* Values are printed exactly as the debugger shows them, including addresses.

### Writing CHECK lines

Put the CHECK lines right after the call and pin the header to it with
`[[@LINE-1]]` (FileCheck doesn't allow `@LINE` in `CHECK-LABEL`, so use
`CHECK`):

```cpp
check_visualizer(hello);
// CHECK: check_visualizer(hello) at test_strings.cpp:[[@LINE-1]]
// CHECK-NEXT:   {{0x[0-9a-f]+}} "hello" [mylib::String]
// CHECK-NEXT:     [size] = 5 [std::size_t]
```

* Use `CHECK-NEXT` to fix the structure, and plain `CHECK` to skip lines, such
  as the elements of a long array.
* Match addresses with a regex: `{{0x[0-9a-f]+}}`.
* natvistest doesn't flag evaluation errors or unreached calls itself. A failed
  natvis expression shows as `-var-create: unable to create variable object` in
  place of the value, and an unreached call prints nothing, so give every call
  CHECK lines that pin the values you care about. Avoid patterns such as
  `{{.*}}` on values, which would also match the error text.
* FileCheck ignores differences in amounts of whitespace, so indentation is
  not checked exactly; `CHECK-NEXT` chains still pin the order of the lines.
* Calls in other functions print when that function runs, so their CHECK
  lines go in execution order, which may not be source order. See `greet()` in
  `example/tests/test_strings.cpp`.

### Finding out what the debugger shows

Run `natvistest run` without piping into FileCheck to see the output to write
CHECK lines against.

## Running

```
python3 -m natvistest run --adapter PATH --natvis FILE.natvis [options] TEST.cpp PROGRAM \
    | FileCheck TEST.cpp
```

`TEST.cpp` is the test source: its `check_visualizer(x);` lines get
breakpoints. Calls in other files of the program are not breakpoints.

| Option | Meaning |
|---|---|
| `--adapter PATH` | **required**: OpenDebugAD7 to use (see below) |
| `--natvis FILE` | **required**: the natvis file under test (if repeated, the last one is used) |
| `--trace` | dump DAP traffic to stderr |

Use `set -o pipefail` (or check both exit codes) when piping by hand, so an
error from natvistest isn't hidden by a passing FileCheck. `pip install .`
installs a `natvistest` command.

There is no timeout: natvistest waits as long as the program runs; stop it
with Ctrl+C. natvistest doesn't handle signals itself. When it exits, the
debug adapter's input closes, and the adapter is expected to shut down, taking
gdb and the program with it. Current OpenDebugAD7 releases don't do this:
they keep running (with gdb and the program) when their input closes. The
issue is drafted in `mi-engine-issue/`, with a reproduction. Until it is fixed,
Ctrl+C in a terminal still cleans up (the adapter receives the SIGINT too),
but killing natvistest alone, e.g. with SIGTERM, leaves those processes
behind.

### CMake / CTest

```cmake
list(APPEND CMAKE_MODULE_PATH path/to/natvistest/cmake)
include(NatvisTest)
enable_testing()

natvis_add_test(test_containers
  SOURCES tests/test_containers.cpp
  NATVIS natvis/mylib.natvis
  LINK_LIBRARIES mylib)
```

This builds the program with `-O0 -g` and registers a CTest test
`natvis.test_containers` (label `natvis`). The test pipes natvistest's
output into FileCheck and fails unless both succeed. The first file in
`SOURCES` is the test source: its `check_visualizer` lines are breakpoints and
it holds the CHECK lines. Both tools' paths must be set
when configuring; configuration fails without them. See `example/` for a
complete project:

```
cmake -S example -B build \
    -DNATVISTEST_ADAPTER=/path/to/OpenDebugAD7 \
    -DNATVISTEST_FILECHECK=/usr/lib/llvm-18/bin/FileCheck
cmake --build build && ctest --test-dir build -L natvis
```

## Getting the debug adapter

`natvistest` never searches for the adapter: `--adapter` must be the path of
an `OpenDebugAD7` executable (or `OpenDebugAD7.dll`, run with `dotnet`).

* **Developer machines**: use the adapter of your installed C/C++
  extension, e.g.
  `~/.vscode/extensions/ms-vscode.cpptools-<version>-linux-x64/debugAdapters/bin/OpenDebugAD7`
  (`~/.vscode-server/...` for Remote SSH). You then test exactly the version
  you debug with.
* **CI**: the extension's license only covers use with Microsoft
  products (VS Code, Visual Studio, …). Build OpenDebugAD7 from the
  MIT-licensed MIEngine sources instead:

  ```
  scripts/build-miengine.sh .miengine        # needs git and the .NET 8 SDK
  natvistest run --adapter .miengine/OpenDebugAD7 ...   # needs the .NET 8 runtime
  ```

  The source-built adapter produced the same results as the one in cpptools
  1.34.4 on the example and self-tests.

## Self-tests

```
python3 -m selftest --adapter /path/to/OpenDebugAD7
```

The tests of the `check_visualizer` line scanner always run. The
integration tests need `--adapter`, gdb and g++/clang++, and are skipped
otherwise. They check the printed trees (including unexpanded children,
nested `[More...]` pages, calls in loops and calls never reached), how broken
natvis shows in them (evaluation errors, a dropped `Expand`), and the errors
natvistest reports (malformed XML, crashes).

## Limitations

* The debugger is always the `gdb` found on `PATH`; lldb is not supported.
* Windows' `cppvsdbg` / Visual Studio natvis is a different engine and is not
  tested by this tool.
