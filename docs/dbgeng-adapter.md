# DbgEng adapter

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
  integers in decimal and characters followed by the character (e.g. `104 'h'`), and children are
  the visualizer's items and elements, or otherwise the fields (not the static ones).
