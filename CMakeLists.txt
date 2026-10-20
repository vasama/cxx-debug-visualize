# Builds the self-tests' fixture program and runs the self-tests with CTest:
#
#   cmake -S . -B build [-DCXX_DEBUG_VISUALIZE_ADAPTER=/path/to/OpenDebugAD7]
#   cmake --build build
#   ctest --test-dir build --output-on-failure
#
# The self-tests compile nothing themselves: CMake builds selftest/fixtures/prog.cpp and passes
# the program to them.
#
# Cache variables:
#   CXX_DEBUG_VISUALIZE_ADAPTER       path to OpenDebugAD7, for the tests that use it
#   CXX_DEBUG_VISUALIZE_FAIL_ON_SKIP  fail if any self-test is skipped, e.g. because a tool is
#                                     missing (default: OFF)

cmake_minimum_required(VERSION 3.16)
project(cxx-debug-visualize LANGUAGES CXX)

find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)

set(CXX_DEBUG_VISUALIZE_ADAPTER "" CACHE FILEPATH "Path to OpenDebugAD7")
option(CXX_DEBUG_VISUALIZE_FAIL_ON_SKIP "Fail if any self-test is skipped" OFF)

enable_testing()

# The fixture program, without optimizations and with debug info.
add_executable(selftest-prog selftest/fixtures/prog.cpp)
target_include_directories(selftest-prog PRIVATE include)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(selftest-prog PRIVATE -O0 -g)
endif()

set(selftest_args --program "$<TARGET_FILE:selftest-prog>")
if(CXX_DEBUG_VISUALIZE_ADAPTER)
  list(APPEND selftest_args --adapter "${CXX_DEBUG_VISUALIZE_ADAPTER}")
endif()
if(CXX_DEBUG_VISUALIZE_FAIL_ON_SKIP)
  list(APPEND selftest_args --fail-on-skip)
endif()

# Run from the source tree, where the selftest and cxx_debug_visualize packages are.
add_test(NAME selftest
         COMMAND "${Python3_EXECUTABLE}" -m selftest ${selftest_args}
         WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
set_tests_properties(selftest PROPERTIES LABELS selftest)
