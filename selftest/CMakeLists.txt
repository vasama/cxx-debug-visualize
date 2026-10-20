# The self-tests, as CTest tests.
#
# The self-tests compile nothing themselves: CMake builds fixtures/prog.cpp and passes the program
# to them. Each self-test is a CTest test of its own, named by its unittest ID (e.g.
# selftest.test_scan.DiscoverTestLinesTests.test_only_whole_line_calls). They are listed when
# CMake configures, which a build redoes when a file in this directory changes. A skipped test is
# reported as skipped.
#
# Cache variables:
#   CXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER  path to OpenDebugAD7, for the tests that use it
#   CXX_DEBUG_VISUALIZE_FAIL_ON_SKIP     fail a self-test that is skipped, e.g. because a tool is
#                                        missing, instead of reporting it as skipped (default: OFF)

find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)

set(CXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER "" CACHE FILEPATH "Path to OpenDebugAD7")
option(CXX_DEBUG_VISUALIZE_FAIL_ON_SKIP "Fail if any self-test is skipped" OFF)

# The fixture program, without optimizations and with debug info.
add_executable(selftest-prog fixtures/prog.cpp)
target_include_directories(selftest-prog PRIVATE "${PROJECT_SOURCE_DIR}/include")
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(selftest-prog PRIVATE -O0 -g)
endif()

set(selftest_args --program "$<TARGET_FILE:selftest-prog>")
if(CXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER)
  list(APPEND selftest_args --vs-code-adapter "${CXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER}")
endif()
if(CXX_DEBUG_VISUALIZE_FAIL_ON_SKIP)
  list(APPEND selftest_args --fail-on-skip)
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
           WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}")
  set_tests_properties("${test}" PROPERTIES LABELS selftest)
  # unittest reports a skipped test as "OK (skipped=1)".
  if(NOT CXX_DEBUG_VISUALIZE_FAIL_ON_SKIP)
    set_tests_properties("${test}" PROPERTIES SKIP_REGULAR_EXPRESSION "OK \\(skipped=")
  endif()
endforeach()
