# The self-tests, as CTest tests.
#
# The self-tests compile nothing themselves: CMake builds fixtures/test_program.cpp and passes the
# program to them. Each self-test is a CTest test of its own, named by its unittest ID (e.g.
# selftest.test_scan.DiscoverTestLinesTests.test_only_whole_line_calls). They are listed when
# CMake configures, which a build redoes when a file in this directory changes.
#
# Cache variables, which select the self-tests run (the others are reported as skipped):
#   CXXDV_TEST_VS     test through the Visual Studio debug adapter, OpenDebugAD7 (default: ON);
#                     these tests also need CXXDV_TEST_GDB, as the adapter runs gdb
#   CXXDV_VS_ADAPTER  path to OpenDebugAD7, required with CXXDV_TEST_VS
#   CXXDV_TEST_GDB    test with gdb (default: ON)
#   CXXDV_TEST_LLDB   test with lldb (default: ON)
# The self-tests of each enabled debugger and adapter fail if it is missing.

find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)

set(CXXDV_VS_ADAPTER "" CACHE FILEPATH "Path to OpenDebugAD7")
option(CXXDV_TEST_VS "Test through the Visual Studio debug adapter" ON)
option(CXXDV_TEST_GDB "Test with gdb" ON)
option(CXXDV_TEST_LLDB "Test with lldb" ON)
if(CXXDV_TEST_VS AND NOT CXXDV_VS_ADAPTER)
  message(FATAL_ERROR "set CXXDV_VS_ADAPTER to the path of OpenDebugAD7, e.g. "
                      "-DCXXDV_VS_ADAPTER=<cpptools>/debugAdapters/bin/OpenDebugAD7, "
                      "or turn CXXDV_TEST_VS off")
endif()

# The fixture program needs debug info and no optimizations: CMake's Debug configuration, whatever
# the compiler. A single-configuration generator must build it (CMAKE_BUILD_TYPE); with a
# multi-configuration one, the self-tests exist only in it.
get_property(multi_config GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
string(TOUPPER "${CMAKE_BUILD_TYPE}" build_type)
if(NOT multi_config AND NOT build_type STREQUAL "DEBUG")
  message(FATAL_ERROR "the self-tests need a Debug build: configure with -DCMAKE_BUILD_TYPE=Debug")
endif()
if(multi_config)
  set(debug_only CONFIGURATIONS Debug)
endif()

add_executable(test_program fixtures/test_program.cpp)
target_include_directories(test_program PRIVATE "${PROJECT_SOURCE_DIR}/include")

set(selftest_args --program "$<TARGET_FILE:test_program>")
if(CXXDV_VS_ADAPTER)
  list(APPEND selftest_args --vs-adapter "${CXXDV_VS_ADAPTER}")
endif()
# The integration tests of the debuggers and adapter not tested are skipped.
if(NOT CXXDV_TEST_VS)
  list(APPEND selftest_args --no-vs)
endif()
if(NOT CXXDV_TEST_GDB)
  list(APPEND selftest_args --no-gdb)
endif()
if(NOT CXXDV_TEST_LLDB)
  list(APPEND selftest_args --no-lldb)
endif()

# Every self-test, as `python -m selftest --list` prints them, run from the source tree's root,
# where the selftest and cxx_debug_visualize packages are. Changing the self-tests reruns this.
file(GLOB selftest_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/*.py")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${selftest_sources})
execute_process(
  COMMAND "${Python3_EXECUTABLE}" -m selftest --list
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  OUTPUT_VARIABLE selftests
  RESULT_VARIABLE result)
if(NOT result EQUAL 0)
  message(FATAL_ERROR "listing the self-tests failed (exit status ${result})")
endif()
string(REPLACE "\n" ";" selftests "${selftests}")

foreach(test IN LISTS selftests)
  if(NOT test)
    continue()
  endif()
  add_test(NAME "${test}"
           COMMAND "${Python3_EXECUTABLE}" -m selftest ${selftest_args} --test "${test}"
           WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" ${debug_only})
  # unittest reports a skipped test as "OK (skipped=1)".
  set_tests_properties("${test}" PROPERTIES LABELS selftest
                       SKIP_REGULAR_EXPRESSION "OK \\(skipped=")
endforeach()
