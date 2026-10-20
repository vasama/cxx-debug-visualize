# Builds and runs the self-tests (see selftest/CMakeLists.txt) and the example project's tests
# (see example/CMakeLists.txt) with CTest:
#
#   cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug \
#         -DCXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER=/path/to/OpenDebugAD7
#   cmake --build build
#   ctest --test-dir build --output-on-failure
#
# CXX_DEBUG_VISUALIZE_TEST_VS_CODE, CXX_DEBUG_VISUALIZE_TEST_GDB and CXX_DEBUG_VISUALIZE_TEST_LLDB
# (all ON by default) select the debuggers and adapter tested; OpenDebugAD7 is only needed with
# the first.

cmake_minimum_required(VERSION 3.15)
project(cxx-debug-visualize LANGUAGES CXX)

enable_testing()

add_subdirectory(selftest)
add_subdirectory(example)
