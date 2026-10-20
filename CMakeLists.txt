# Builds and runs the self-tests (see tests/CMakeLists.txt) and the example project's tests
# (see examples/CMakeLists.txt) with CTest:
#
#   cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug \
#         -DCXXDEBVIS_GDB=gdb -DCXXDEBVIS_LLDB_DAP=lldb-dap \
#         -DCXXDEBVIS_MIENGINE=/path/to/OpenDebugAD7
#   cmake --build build
#   ctest --test-dir build --output-on-failure
#
# CXXDEBVIS_GDB, CXXDEBVIS_LLDB_DAP and CXXDEBVIS_MIENGINE give the executables to test with
# (absolute paths, or names looked up on PATH), and so select the tests. -DCXXDEBVIS_TEST_STDLIB=ON
# also tests the debuggers' default visualizers for the standard library (see tests/CMakeLists.txt).
#
# On Windows, with a compiler for the MSVC ABI (MSVC, or Clang targeting MSVC, including clang-cl),
# the dbgeng adapter in cxx_debug_visualize_dbgeng/ is built and tested too, if the Windows debug
# engine is found: by default that of the Debugging Tools for Windows, or the one DbgEng_ROOT names
# (see cxx_debug_visualize_dbgeng/cmake/FindDbgEng.cmake). At least one debugger (gdb, lldb-dap or
# DbgEng) is needed.
#
#   cmake -S . -B build
#   cmake --build build --config Debug
#   ctest --test-dir build -C Debug --output-on-failure

cmake_minimum_required(VERSION 3.15)
project(cxx-debug-visualize LANGUAGES CXX)

enable_testing()

# The dbgeng adapter, if DbgEng is found. The tests use its target, dbgeng-adapter, if there is
# one, with the dbgeng.dll found (DbgEng_DLL).
if(CMAKE_CXX_COMPILER_ID STREQUAL "MSVC" OR CMAKE_CXX_SIMULATE_ID STREQUAL "MSVC")
  list(APPEND CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}/cxx_debug_visualize_dbgeng/cmake")
  find_package(DbgEng)
  if(DbgEng_FOUND)
    add_subdirectory(cxx_debug_visualize_dbgeng)
  else()
    message(STATUS "The dbgeng adapter is not built: install the Debugging Tools for Windows, or "
                   "set DbgEng_ROOT")
  endif()
endif()

add_subdirectory(tests)
add_subdirectory(examples)
