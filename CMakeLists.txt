# Builds and runs the self-tests (see tests/CMakeLists.txt) and the example project's tests
# (see examples/CMakeLists.txt) with CTest:
#
#   cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug -DCXXDV_GDB=gdb -DCXXDV_LLDB_DAP=lldb-dap \
#         -DCXXDV_VS_ADAPTER=/path/to/OpenDebugAD7
#   cmake --build build
#   ctest --test-dir build --output-on-failure
#
# CXXDV_GDB, CXXDV_LLDB_DAP and CXXDV_VS_ADAPTER give the executables to test with (absolute paths,
# or names looked up on PATH), and so select the tests; at least one of the debuggers is needed.

cmake_minimum_required(VERSION 3.15)
project(cxx-debug-visualize LANGUAGES CXX)

enable_testing()

add_subdirectory(tests)
add_subdirectory(examples)
