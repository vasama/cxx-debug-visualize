# `cxx-debug-visualize`: debugger visualizers testing utility

`cxx-debug-visualize` runs a test program under a debugger, and prints visualizations of C++ objects
as defined by the provided visualization script (Natvis, GDB pretty printer, or LLDB formatter).

`cxx-debug-visualize` relies on the now widely supported
[Debug Adapter Protocol](https://microsoft.github.io/debug-adapter-protocol).
* Natvis support is implemented using Visual Studio's open source debug adapter
([`OpenDebugAD7`](https://github.com/microsoft/MIEngine)). On Windows, Natvis can instead be tested
with the Windows debug engine (DbgEng), through the debug adapter in
[`cxx_debug_visualize_dbgeng/`][dbgeng].
* GDB pretty printers can be tested either via the MIEngine adapter, or using GDB's native
  DAP support (GDB 14 or later), although the output between the two adapters may vary.
* LLDB formatters can be tested using LLDB's DAP server (`lldb-dap`, or `lldb-vscode` prior to LLVM
  18).

## Quick Example

```cpp
mylib::vector<int> v;
for (int i = 1; i <= 3; ++i)
  v.push_back(i * 10);

visualize(v);
```

A breakpoint is automatically placed on each line matching an invocation of a function named
`visualize`, and upon breaking a visualization of the named object is printed to stdout:

```
visualize(v) at test_containers.cpp:34
  { size=3 } [mylib::vector<int>]
    [size] = 3 [std::size_t]
    [capacity] = 4 [std::size_t]
    [0] = 10 [int]
    [1] = 20 [int]
    [2] = 30 [int]
```

> **NOTE:** Only full lines containing exactly `visualize(identifier);` and no other non-whitespace
> content are matched. Any other line is silently ignored.

An applicable definition of the `visualize` function can be found in the [header][header], but using
it is not necessary. The user is free to bring their own definition, as long as each invocation
generates executable code where the debugger is able to place a breakpoint. Note that building with
debug information enabled is required for the placement of a breakpoint in the appropriate location.

The method of testing expectations is left up to the user, e.g. by comparing the output against a
file containing expected output, using LLVM `FileCheck` (standalone Python implementation
[here](https://pypi.org/project/filecheck/)), or some other means of parsing. Note in the case that
the output contains addresses, which may be expected to vary from one execution to the next, it is
up to the user to deal with them in the way of their choosing.

See [`examples/`][examples] for a full example testing all supported types of visualizers.

## Installation

```bash
# Using pip:
pip install cxx-debug-visualize

# Using pipx:
pipx install cxx-debug-visualize
```

Python 3.10 or later is required, but otherwise only the standard library is used. Usage requires
`gdb` or `lldb-dap` and optionally `OpenDebugAD7` (for testing Natvis visualizers, only via GDB), or
on Windows the dbgeng adapter (for testing Natvis visualizers with DbgEng).

## Usage

```bash
cxx-debug-visualize test.cpp test_program --natvis my_library.natvis
cxx-debug-visualize test.cpp test_program --gdb-printers my_printers.py
cxx-debug-visualize test.cpp test_program --lldb-formatters my_formatters.py
```

* `test.cpp` is the test source file. It is searched for any occurrences of `visualize(x);` and
  breakpoints are placed on each matching line. A visualization of the specified object is printed
  at each breakpoint.
* The visualizer script under test is specified using at most one of `--natvis`, `--gdb-printers`,
  or `--lldb-formatters`.
* The visualizers that the debugger loads by default (e.g. libstdc++'s pretty printers, LLDB's C++
  formatters, or the Natvis files of the Debugging Tools for Windows) are active alongside the
  visualizer under test (if any). `--no-default-visualizers` disables them, so that only the
  visualizer under test is active.
* The debugger executable to use may be specified using `--debugger-path`. For `dbgeng`, it is the
  directory of `dbgeng.dll` (or a file in it, such as `cdb.exe`), by default that of the Debugging
  Tools for Windows.
* The type of debugger to use may be specified using `--debugger` (`gdb`, `lldb` or `dbgeng`), but
  in most cases it can be selected automatically.
* The type of debug adapter to use may be specified using `--adapter` (`native`, `miengine` or
  `dbgeng`), but in most cases it can be selected automatically. Only the `miengine` and `dbgeng`
  adapters support Natvis, and `dbgeng` supports only Natvis.
* `--miengine` (or `$CXX_DEBUG_VISUALIZE_MIENGINE`) may be used to specify the `OpenDebugAD7`
  executable path. If neither is specified, the user's home directory is searched for an installed
  VS Code C/C++ extension.
* `--dbgeng` (or `$CXX_DEBUG_VISUALIZE_DBGENG`) specifies the dbgeng adapter executable path, and
  selects the `dbgeng` adapter and debugger. It cannot be combined with `--miengine`.
* Unparsed arguments are passed to the test program. Use `--` to escape options.

## Development

### Requirements
* CMake
* C++ compiler
* At least one of:
  * GDB (14 or later for builtin DAP support)
  * LLDB DAP server (`lldb-dap`, previously `lldb-vscode`)
  * Debugging Tools for Windows (DbgEng)
* Optional: MIEngine debug adapter (`OpenDebugAD7`)

### Example commands

```bash
cmake -B build . \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCXXDEBVIS_GDB=gdb \
  -DCXXDEBVIS_LLDB_DAP=lldb-dap-18 \
  -DCXXDEBVIS_MIENGINE=/path/to/OpenDebugAD7

cmake --build build
ctest --test-dir build
```

Use `-DCXXDEBVIS_TEST_STDLIB=ON` to enable testing of builtin visualizers load by the debugger by
default (e.g. libstdc++, libc++ or MSVC's STL). The expected output depends on the versions of the
standard library and the debugger. This is mostly useful for CI where the configuration is stable.

### Debugging

Use the `--trace` option with `cxx-debug-visualize` to print all DAP traffic to stderr.

## Getting `OpenDebugAD7`

* **Developer machines**: it is possible to rely on the debug adapter installed via the VS Code
  C/C++ extension. Otherwise, a specific executable (or .NET `.dll`) may be specified using
  `--miengine`. For remote development (e.g. via SSH), the installed VS Code server extensions are
  also searched.
* **CI**: Build `OpenDebugAD7` from the MIT-licensed
  [MIEngine](https://github.com/microsoft/MIEngine) source (with .NET 8 or later):

  ```
  git clone --depth 1 https://github.com/microsoft/MIEngine.git
  sh MIEngine/PublishOpenDebugAD7.sh -c Release -o "$PWD/miengine"
  cxx-debug-visualize --miengine miengine/OpenDebugAD7 ...
  ```

  The build is self-contained: it includes the .NET runtime, so running it needs no .NET
  installation. Give `-o` an absolute path, since the script changes to its own directory. See the
  [test workflow][test_workflow] for a full CI example.

## Limitations

* `lldb` with the MIEngine debug adapter is currently unsupported (VS Code on macOS).
* `cppvsdbg` uses a different engine and is currently unsupported (Visual Studio Natvis).

## License

`cxx-debug-visualize` is free software: you can redistribute it and/or modify it under the terms of
the GNU General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version. See [LICENSE.md][license] for the full text.

The exception is [`include/cxx_debug_visualize.hpp`][header], which test programs may include
(although doing so is not necessary). This header is licensed under the MIT No Attribution License
(MIT-0, see [LICENSE-MIT-0][license-mit-0]), meaning it can be used, copied and changed freely,
without any attribution requirements.

[header]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/include/cxx_debug_visualize.hpp
[examples]: https://github.com/vasama/cxx-debug-visualize/tree/HEAD/examples/
[dbgeng]: https://github.com/vasama/cxx-debug-visualize/tree/HEAD/cxx_debug_visualize_dbgeng/
[license]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/LICENSE.md
[license-mit-0]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/LICENSE-MIT-0
[test_workflow]: https://github.com/vasama/cxx-debug-visualize/blob/HEAD/.github/workflows/test.yml
