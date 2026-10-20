# Builds the self-tests' fixture program and runs the self-tests with CTest (see
# selftest/CMakeLists.txt):
#
#   cmake -S . -B build [-DCXX_DEBUG_VISUALIZE_ADAPTER=/path/to/OpenDebugAD7]
#   cmake --build build
#   ctest --test-dir build --output-on-failure

cmake_minimum_required(VERSION 3.15)
project(cxx-debug-visualize LANGUAGES CXX)

enable_testing()
add_subdirectory(selftest)
