# The self-tests, as CTest tests.
#
# The self-tests compile nothing themselves: CMake builds fixtures/test_program.cpp and passes the
# program to them. Each self-test is a CTest test of its own, named by its unittest ID (e.g.
# tests.test_scan.DiscoverTestLinesTests.test_only_whole_line_calls). They are listed when
# CMake configures, which a build redoes when a file in this directory changes.
#
# Cache variables, the executables to test with, which select the self-tests registered:
#   CXXDV_GDB         gdb, for the tests with gdb, natively (GDB 14 and later) and through
#                     OpenDebugAD7
#   CXXDV_LLDB_DAP    lldb-dap (or lldb-vscode), for the tests with lldb
#   CXXDV_VS_ADAPTER  OpenDebugAD7, the Visual Studio debug adapter, for the tests through it;
#                     needs CXXDV_GDB, as the adapter runs gdb
# Each is an absolute path, or a name looked up on PATH; unset, the tests that need it are not
# registered. At least one of CXXDV_GDB and CXXDV_LLDB_DAP must be set.

find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)

set(CXXDV_GDB "" CACHE STRING "gdb: an absolute path, or a name looked up on PATH")
set(CXXDV_LLDB_DAP "" CACHE STRING "lldb-dap: an absolute path, or a name looked up on PATH")
set(CXXDV_VS_ADAPTER "" CACHE STRING "OpenDebugAD7: an absolute path, or a name looked up on PATH")

# The full path of each executable given, as <variable>_PATH; empty if not given.
foreach(cxxdv_var IN ITEMS CXXDV_GDB CXXDV_LLDB_DAP CXXDV_VS_ADAPTER)
  set(cxxdv_value "${${cxxdv_var}}")
  set(${cxxdv_var}_PATH "")
  if(cxxdv_value STREQUAL "")
    continue()
  elseif(IS_ABSOLUTE "${cxxdv_value}")
    if(NOT EXISTS "${cxxdv_value}" OR IS_DIRECTORY "${cxxdv_value}")
      message(FATAL_ERROR "${cxxdv_var}: ${cxxdv_value} is not a file")
    endif()
    set(${cxxdv_var}_PATH "${cxxdv_value}")
  elseif(cxxdv_value MATCHES "[/\\\\]")
    message(FATAL_ERROR "${cxxdv_var}: ${cxxdv_value} is neither an absolute path nor a name")
  else()
    unset(cxxdv_found CACHE)
    find_program(cxxdv_found NAMES "${cxxdv_value}" NO_DEFAULT_PATH PATHS ENV PATH)
    if(NOT cxxdv_found)
      message(FATAL_ERROR "${cxxdv_var}: ${cxxdv_value} not found on PATH")
    endif()
    set(${cxxdv_var}_PATH "${cxxdv_found}")
    unset(cxxdv_found CACHE)
  endif()
endforeach()
if(NOT CXXDV_GDB_PATH AND NOT CXXDV_LLDB_DAP_PATH)
  message(FATAL_ERROR "set CXXDV_GDB, CXXDV_LLDB_DAP or both to the debuggers to test with, e.g. "
                      "-DCXXDV_GDB=gdb -DCXXDV_LLDB_DAP=lldb-dap")
endif()
if(CXXDV_VS_ADAPTER_PATH AND NOT CXXDV_GDB_PATH)
  message(FATAL_ERROR "CXXDV_VS_ADAPTER needs CXXDV_GDB, as OpenDebugAD7 runs gdb")
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

# The executables to test with; --list leaves out the integration tests of those not given.
set(selftest_tools "")
if(CXXDV_GDB_PATH)
  list(APPEND selftest_tools --gdb "${CXXDV_GDB_PATH}")
endif()
if(CXXDV_LLDB_DAP_PATH)
  list(APPEND selftest_tools --lldb-dap "${CXXDV_LLDB_DAP_PATH}")
endif()
if(CXXDV_VS_ADAPTER_PATH)
  list(APPEND selftest_tools --vs-adapter "${CXXDV_VS_ADAPTER_PATH}")
endif()
set(selftest_args --program "$<TARGET_FILE:test_program>" ${selftest_tools})

# Every self-test of the executables given, as `python -m tests --list` prints them, run from
# the source tree's root, where the tests and cxx_debug_visualize packages are. Changing the
# self-tests reruns this.
file(GLOB selftest_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/*.py")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${selftest_sources})
execute_process(
  COMMAND "${Python3_EXECUTABLE}" -m tests ${selftest_tools} --list
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
           COMMAND "${Python3_EXECUTABLE}" -m tests ${selftest_args} --test "${test}"
           WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" ${debug_only})
  # unittest reports a skipped test (e.g. one that doesn't apply to the platform) as
  # "OK (skipped=1)".
  set_tests_properties("${test}" PROPERTIES LABELS selftest
                       SKIP_REGULAR_EXPRESSION "OK \\(skipped=")
endforeach()
