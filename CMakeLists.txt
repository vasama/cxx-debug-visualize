# Builds and runs the self-tests (see selftest/CMakeLists.txt) and the example project's tests
# (see example/CMakeLists.txt) with CTest:
#
#   cmake -S . -B build [-DCXX_DEBUG_VISUALIZE_ADAPTER=/path/to/OpenDebugAD7]
#   cmake --build build
#   ctest --test-dir build --output-on-failure

cmake_minimum_required(VERSION 3.15)
project(cxx-debug-visualize LANGUAGES CXX)

enable_testing()
add_subdirectory(selftest)
add_subdirectory(example)
