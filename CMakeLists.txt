# Builds and runs the self-tests (see tests/CMakeLists.txt) and the example project's tests
# (see examples/CMakeLists.txt) with CTest:
#
#   cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug \
#         -DCXXDEBVIS_GDB=gdb -DCXXDEBVIS_LLDB_DAP=lldb-dap \
#         -DCXXDEBVIS_MIENGINE=/path/to/OpenDebugAD7
#   cmake --build build
#   ctest --test-dir build --output-on-failure
#
# CXXDEBVIS_GDB, CXXDEBVIS_LLDB_DAP, CXXDEBVIS_MIENGINE and CXXDEBVIS_DBGENG give the executables to
# test with (absolute paths, or names looked up on PATH), and so select the tests; at least one of
# the debuggers (gdb, lldb-dap or dbgeng-adapter) is needed. On Windows, with the dbgeng adapter
# built from dbgeng-adapter/:
#
#   cmake -S . -B build -DCXXDEBVIS_DBGENG=C:/path/to/dbgeng-adapter.exe
#   cmake --build build --config Debug
#   ctest --test-dir build -C Debug --output-on-failure

cmake_minimum_required(VERSION 3.15)
project(cxx-debug-visualize LANGUAGES CXX)

enable_testing()

add_subdirectory(tests)
add_subdirectory(examples)
