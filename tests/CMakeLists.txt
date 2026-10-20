# The self-tests, as CTest tests.
#
# The self-tests compile nothing themselves: CMake builds fixtures/test_program.cpp and passes the
# program to them. Each self-test is a CTest test of its own, named by its unittest ID (e.g.
# tests.test_scan.DiscoverTestLinesTests.test_only_whole_line_calls). They are listed when
# CMake configures, which a build redoes when a file in this directory changes.
#
# Cache variables, the executables to test with, which select the self-tests registered:
#   CXXDEBVIS_GDB       gdb, for the tests with gdb, natively (GDB 14 and later) and through
#                       OpenDebugAD7
#   CXXDEBVIS_LLDB_DAP  lldb-dap (or lldb-vscode), for the tests with lldb
#   CXXDEBVIS_MIENGINE  OpenDebugAD7, MIEngine's debug adapter, for the tests through it; needs
#                       CXXDEBVIS_GDB, as the adapter runs gdb
#   CXXDEBVIS_DBGENG    dbgeng-adapter (see dbgeng-adapter/), for the tests with the Windows debug
#                       engine (DbgEng)
# Each is an absolute path, or a name looked up on PATH; unset, the tests that need it are not
# registered. At least one of CXXDEBVIS_GDB, CXXDEBVIS_LLDB_DAP and CXXDEBVIS_DBGENG must be set.
#
# CXXDEBVIS_TEST_STDLIB (default OFF) also registers the standard library tests (see below).

find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)

set(CXXDEBVIS_GDB "" CACHE STRING "gdb: an absolute path, or a name looked up on PATH")
set(CXXDEBVIS_LLDB_DAP "" CACHE STRING "lldb-dap: an absolute path, or a name looked up on PATH")
set(CXXDEBVIS_MIENGINE ""
    CACHE STRING "OpenDebugAD7: an absolute path, or a name looked up on PATH")
set(CXXDEBVIS_DBGENG ""
    CACHE STRING "dbgeng-adapter: an absolute path, or a name looked up on PATH")

# The full path of each executable given, as <variable>_PATH; empty if not given.
foreach(cxxdebvis_var IN ITEMS CXXDEBVIS_GDB CXXDEBVIS_LLDB_DAP CXXDEBVIS_MIENGINE
                               CXXDEBVIS_DBGENG)
  set(cxxdebvis_value "${${cxxdebvis_var}}")
  set(${cxxdebvis_var}_PATH "")
  if(cxxdebvis_value STREQUAL "")
    continue()
  elseif(IS_ABSOLUTE "${cxxdebvis_value}")
    if(NOT EXISTS "${cxxdebvis_value}" OR IS_DIRECTORY "${cxxdebvis_value}")
      message(FATAL_ERROR "${cxxdebvis_var}: ${cxxdebvis_value} is not a file")
    endif()
    set(${cxxdebvis_var}_PATH "${cxxdebvis_value}")
  elseif(cxxdebvis_value MATCHES "[/\\\\]")
    message(FATAL_ERROR
            "${cxxdebvis_var}: ${cxxdebvis_value} is neither an absolute path nor a name")
  else()
    unset(cxxdebvis_found CACHE)
    find_program(cxxdebvis_found NAMES "${cxxdebvis_value}" NO_DEFAULT_PATH PATHS ENV PATH)
    if(NOT cxxdebvis_found)
      message(FATAL_ERROR "${cxxdebvis_var}: ${cxxdebvis_value} not found on PATH")
    endif()
    set(${cxxdebvis_var}_PATH "${cxxdebvis_found}")
    unset(cxxdebvis_found CACHE)
  endif()
endforeach()
if(NOT CXXDEBVIS_GDB_PATH AND NOT CXXDEBVIS_LLDB_DAP_PATH AND NOT CXXDEBVIS_DBGENG_PATH)
  message(FATAL_ERROR "set one or more of CXXDEBVIS_GDB, CXXDEBVIS_LLDB_DAP and CXXDEBVIS_DBGENG "
                      "to the debuggers to test with, e.g. -DCXXDEBVIS_GDB=gdb")
endif()
if(CXXDEBVIS_MIENGINE_PATH AND NOT CXXDEBVIS_GDB_PATH)
  message(FATAL_ERROR "CXXDEBVIS_MIENGINE needs CXXDEBVIS_GDB, as OpenDebugAD7 runs gdb")
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
if(CXXDEBVIS_GDB_PATH)
  list(APPEND selftest_tools --gdb "${CXXDEBVIS_GDB_PATH}")
endif()
if(CXXDEBVIS_LLDB_DAP_PATH)
  list(APPEND selftest_tools --lldb-dap "${CXXDEBVIS_LLDB_DAP_PATH}")
endif()
if(CXXDEBVIS_MIENGINE_PATH)
  list(APPEND selftest_tools --miengine "${CXXDEBVIS_MIENGINE_PATH}")
endif()
if(CXXDEBVIS_DBGENG_PATH)
  list(APPEND selftest_tools --dbgeng "${CXXDEBVIS_DBGENG_PATH}")
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

# The standard library tests, with CXXDEBVIS_TEST_STDLIB: the visualizers that the debuggers load
# by default for the standard library that the compiler uses (libstdc++, libc++ or MSVC's STL, told
# apart by the macros its headers define). fixtures/standard_types.cpp, built as C++17, runs under
# cxx-debug-visualize without a visualizer under test, and its output is compared with
# fixtures/standard_types.<library>-<kind>.txt (by compare_output.py, as the example's tests
# compare theirs), e.g. standard_types.libstdc++-gdb-native.txt. The tests, labelled "stdlib":
#   stdlib.gdb-native     libstdc++'s pretty printers, through gdb's own DAP support
#   stdlib.gdb-miengine   libstdc++'s pretty printers, through OpenDebugAD7
#   stdlib.lldb-native    lldb's formatters for the library, through lldb-dap
#   stdlib.natvis-dbgeng  the Debugging Tools' natvis files for MSVC's STL, through dbgeng-adapter
# Neither libc++'s gdb pretty printers nor natvis files for MIEngine are installed by default, so
# there are no tests of them. The output depends on the versions of the library and the debugger.
option(CXXDEBVIS_TEST_STDLIB
       "Test the visualizers that the debuggers load by default for the standard library" OFF)
if(CXXDEBVIS_TEST_STDLIB)
  include(CheckCXXSymbolExists)
  check_cxx_symbol_exists(__GLIBCXX__ utility cxxdebvis_libstdcxx)
  check_cxx_symbol_exists(_LIBCPP_VERSION utility cxxdebvis_libcxx)
  check_cxx_symbol_exists(_MSVC_STL_VERSION utility cxxdebvis_msstl)
  if(cxxdebvis_libstdcxx)
    set(stdlib libstdc++)
  elseif(cxxdebvis_libcxx)
    set(stdlib libc++)
  elseif(cxxdebvis_msstl)
    set(stdlib msstl)
  else()
    message(FATAL_ERROR "CXXDEBVIS_TEST_STDLIB: the standard library is not libstdc++, libc++ or "
                        "MSVC's STL")
  endif()
  message(STATUS "Standard library under test: ${stdlib}")

  find_package(Threads REQUIRED)
  add_executable(standard_types fixtures/standard_types.cpp)
  target_include_directories(standard_types PRIVATE "${PROJECT_SOURCE_DIR}/include")
  target_link_libraries(standard_types PRIVATE Threads::Threads)
  set_target_properties(standard_types PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON
                                                  CXX_EXTENSIONS OFF)

  # Register the CTest test stdlib.<kind>, which runs standard_types for the kind of visualizers
  # <visualizer> (gdb, lldb or natvis), under cxx-debug-visualize with the options that follow.
  function(add_stdlib_test kind visualizer)
    add_test(NAME stdlib.${kind}
             COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/compare_output.py"
                     "${CMAKE_CURRENT_SOURCE_DIR}/fixtures/standard_types.${stdlib}-${kind}.txt"
                     "${CMAKE_CURRENT_BINARY_DIR}/stdlib.${kind}.actual.txt"
                     "${Python3_EXECUTABLE}" -m cxx_debug_visualize ${ARGN}
                     "${CMAKE_CURRENT_SOURCE_DIR}/fixtures/standard_types.cpp"
                     "$<TARGET_FILE:standard_types>" ${stdlib} ${visualizer}
             WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" ${debug_only})
    set_tests_properties(stdlib.${kind} PROPERTIES LABELS stdlib)
  endfunction()

  set(gdb --debugger gdb --debugger-path "${CXXDEBVIS_GDB_PATH}")
  if(stdlib STREQUAL "libstdc++" AND CXXDEBVIS_GDB_PATH)
    add_stdlib_test(gdb-native gdb --adapter native ${gdb})
  endif()
  if(stdlib STREQUAL "libstdc++" AND CXXDEBVIS_MIENGINE_PATH)
    add_stdlib_test(gdb-miengine gdb --adapter miengine --miengine "${CXXDEBVIS_MIENGINE_PATH}"
                    ${gdb})
  endif()
  if(CXXDEBVIS_LLDB_DAP_PATH)
    add_stdlib_test(lldb-native lldb --debugger lldb --debugger-path "${CXXDEBVIS_LLDB_DAP_PATH}")
  endif()
  if(stdlib STREQUAL "msstl" AND CXXDEBVIS_DBGENG_PATH)
    add_stdlib_test(natvis-dbgeng natvis --dbgeng "${CXXDEBVIS_DBGENG_PATH}")
  endif()
endif()
