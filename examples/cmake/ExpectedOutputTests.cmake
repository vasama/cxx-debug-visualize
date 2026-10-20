# This example's way of testing visualizers: comparing cxx-debug-visualize's output with expected
# output files. It runs cxx-debug-visualize from this checkout of its repository.
#
#   add_visualizer_test(<name>
#     SOURCES <test.cpp>...              # the first one is the test source
#     [NATVIS <file.natvis>]             # natvis file under test
#     [GDB_PRINTERS <printers.py>]       # gdb pretty-printer script under test
#     [LLDB_FORMATTERS <formatters.py>]  # lldb formatter script under test
#     [LINK_LIBRARIES <lib>...]
#     [INCLUDE_DIRECTORIES <dir>...]
#     [ARGS <option>...]                 # cxx-debug-visualize options, e.g. --trace
#   )
#
# Builds the program <name> with the repository's include/ directory, for cxx_debug_visualize.hpp,
# and registers CTest tests labelled
# "visualizers", which run <name> under cxx-debug-visualize:
#   natvis.<name>       NATVIS, through the Visual Studio debug adapter (OpenDebugAD7)
#   gdb-vs.<name>       GDB_PRINTERS, through OpenDebugAD7
#   gdb-native.<name>   GDB_PRINTERS, through gdb's own DAP support (GDB 14 and later)
#   lldb-native.<name>  LLDB_FORMATTERS, through lldb-dap (lldb-vscode before LLVM 18)
# Each compares the printed Variables trees with an expected output file next to the test
# source, the first file in SOURCES: <test>.<kind>.txt, e.g. <test>.natvis.txt,
# <test>.gdb-vs.txt, <test>.gdb-native.txt and <test>.lldb-native.txt for tests/<test>.cpp.
#
# Addresses differ between machines, so every hexadecimal number (0x...) in the output is
# replaced by "0x?" before comparing; expected files contain "0x?" in their place.  Line endings
# are ignored, as they differ between platforms (e.g. Python writes \r\n on Windows, and git may
# check out expected files with either).  A test fails if cxx-debug-visualize fails or the output
# differs from the expected file (or that is missing). The actual output is then written to
# <kind>.<name>.actual.txt in the build directory, with \n line endings, for review or to copy over
# the expected file, and a diff is printed.
#
# Cache variables, the executables to test with, which select the tests registered:
#   CXXDEBVIS_GDB         gdb, for the tests with gdb, natively (GDB 14 and later) and through
#                         OpenDebugAD7
#   CXXDEBVIS_LLDB_DAP    lldb-dap (or lldb-vscode), for the tests with lldb
#   CXXDEBVIS_VS_ADAPTER  OpenDebugAD7, the Visual Studio debug adapter, for the tests through
#                         it; needs CXXDEBVIS_GDB, as the adapter runs gdb
# Each is an absolute path, or a name looked up on PATH; unset, the tests that need it are not
# registered. At least one of CXXDEBVIS_GDB and CXXDEBVIS_LLDB_DAP must be set.
#
# The test programs need debug info and no optimizations, so that each `visualize(x);` line
# compiles to code of its own: CMake's Debug configuration, whatever the compiler. A
# single-configuration generator must build it (CMAKE_BUILD_TYPE); with a multi-configuration one,
# the tests exist only in it.

find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)

get_filename_component(CXX_DEBUG_VISUALIZE_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
set(CXX_DEBUG_VISUALIZE_COMMAND
    "${CMAKE_COMMAND}" -E env "PYTHONPATH=${CXX_DEBUG_VISUALIZE_ROOT}"
    "${Python3_EXECUTABLE}" -m cxx_debug_visualize)

set(CXXDEBVIS_GDB "" CACHE STRING "gdb: an absolute path, or a name looked up on PATH")
set(CXXDEBVIS_LLDB_DAP "" CACHE STRING "lldb-dap: an absolute path, or a name looked up on PATH")
set(CXXDEBVIS_VS_ADAPTER ""
    CACHE STRING "OpenDebugAD7: an absolute path, or a name looked up on PATH")

# The full path of each executable given, as <variable>_PATH; empty if not given.
foreach(cxxdebvis_var IN ITEMS CXXDEBVIS_GDB CXXDEBVIS_LLDB_DAP CXXDEBVIS_VS_ADAPTER)
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
if(NOT CXXDEBVIS_GDB_PATH AND NOT CXXDEBVIS_LLDB_DAP_PATH)
  message(FATAL_ERROR "set CXXDEBVIS_GDB, CXXDEBVIS_LLDB_DAP or both to the debuggers to test "
                      "with, e.g. -DCXXDEBVIS_GDB=gdb -DCXXDEBVIS_LLDB_DAP=lldb-dap")
endif()
if(CXXDEBVIS_VS_ADAPTER_PATH AND NOT CXXDEBVIS_GDB_PATH)
  message(FATAL_ERROR "CXXDEBVIS_VS_ADAPTER needs CXXDEBVIS_GDB, as OpenDebugAD7 runs gdb")
endif()

get_property(_visualizer_test_multi_config GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
string(TOUPPER "${CMAKE_BUILD_TYPE}" _visualizer_test_build_type)
if(NOT _visualizer_test_multi_config AND NOT _visualizer_test_build_type STREQUAL "DEBUG")
  message(FATAL_ERROR "the visualizer tests need a Debug build: configure with "
                      "-DCMAKE_BUILD_TYPE=Debug")
endif()

# Prints a unified diff of an expected file (possibly missing) and the actual output.
set(_VISUALIZER_TEST_DIFF "import difflib, os, sys
expected, actual = sys.argv[1:]
old = open(expected).readlines() if os.path.exists(expected) else []
sys.stdout.writelines(difflib.unified_diff(old, open(actual).readlines(), expected, actual))")

function(add_visualizer_test name)
  cmake_parse_arguments(PARSE_ARGV 1 TV "" "NATVIS;GDB_PRINTERS;LLDB_FORMATTERS"
                        "SOURCES;LINK_LIBRARIES;INCLUDE_DIRECTORIES;ARGS")
  if(NOT TV_SOURCES)
    message(FATAL_ERROR "add_visualizer_test(${name}): SOURCES is required")
  endif()
  if(NOT TV_NATVIS AND NOT TV_GDB_PRINTERS AND NOT TV_LLDB_FORMATTERS)
    message(FATAL_ERROR "add_visualizer_test(${name}): NATVIS, GDB_PRINTERS or "
                        "LLDB_FORMATTERS is required")
  endif()

  add_executable(${name} ${TV_SOURCES})
  target_include_directories(${name} PRIVATE "${CXX_DEBUG_VISUALIZE_ROOT}/include"
                             ${TV_INCLUDE_DIRECTORIES})
  if(TV_LINK_LIBRARIES)
    target_link_libraries(${name} PRIVATE ${TV_LINK_LIBRARIES})
  endif()

  list(GET TV_SOURCES 0 test_source)
  get_filename_component(test_source "${test_source}" ABSOLUTE)

  set(gdb --debugger gdb --debugger-path "${CXXDEBVIS_GDB_PATH}")
  if(TV_NATVIS AND CXXDEBVIS_VS_ADAPTER_PATH)
    _add_visualizer_run(natvis ${name} "${test_source}" vs
                        --natvis "${TV_NATVIS}" ${gdb} ${TV_ARGS})
  endif()
  if(TV_GDB_PRINTERS AND CXXDEBVIS_VS_ADAPTER_PATH)
    _add_visualizer_run(gdb-vs ${name} "${test_source}" vs
                        --gdb-printers "${TV_GDB_PRINTERS}" ${gdb} ${TV_ARGS})
  endif()
  if(TV_GDB_PRINTERS AND CXXDEBVIS_GDB_PATH)
    _add_visualizer_run(gdb-native ${name} "${test_source}" native
                        --gdb-printers "${TV_GDB_PRINTERS}" ${gdb} ${TV_ARGS})
  endif()
  if(TV_LLDB_FORMATTERS AND CXXDEBVIS_LLDB_DAP_PATH)
    _add_visualizer_run(lldb-native ${name} "${test_source}" native
                        --lldb-formatters "${TV_LLDB_FORMATTERS}"
                        --debugger lldb --debugger-path "${CXXDEBVIS_LLDB_DAP_PATH}" ${TV_ARGS})
  endif()
endfunction()

# Register the CTest test "<kind>.<name>", which runs the program <name> with --adapter <adapter>
# (native or vs) and the visualizer <option> <file>, and compares the output with
# <test source>.<kind>.txt.  Further arguments are passed on to cxx-debug-visualize.
function(_add_visualizer_run kind name test_source adapter option file)
  get_filename_component(file "${file}" ABSOLUTE)
  get_filename_component(test_dir "${test_source}" DIRECTORY)
  get_filename_component(test_name "${test_source}" NAME_WE)
  set(expected "${test_dir}/${test_name}.${kind}.txt")
  set(actual "${CMAKE_CURRENT_BINARY_DIR}/${kind}.${name}.actual.txt")
  set(run ${CXX_DEBUG_VISUALIZE_COMMAND} --adapter ${adapter})
  if(adapter STREQUAL "vs")
    list(APPEND run --vs-adapter "${CXXDEBVIS_VS_ADAPTER_PATH}")
  endif()
  list(APPEND run ${option} "${file}" ${ARGN} "${test_source}")

  # A CTest test is a single command, so the comparison runs from a generated script. The program
  # is passed to it as `program`, as its path depends on the configuration.
  set(run_quoted "")
  foreach(arg IN LISTS run)
    string(APPEND run_quoted " \"${arg}\"")
  endforeach()
  set(script "${CMAKE_CURRENT_BINARY_DIR}/${kind}-${name}.cmake")
  file(GENERATE OUTPUT "${script}" CONTENT
"execute_process(
  COMMAND${run_quoted} \"\${program}\"
  OUTPUT_VARIABLE output
  RESULT_VARIABLE result)
string(REGEX REPLACE \"0x[0-9a-fA-F]+\" \"0x?\" output \"\${output}\")
string(REPLACE \"\\r\\n\" \"\\n\" output \"\${output}\")
set(expected_output \"\")
if(EXISTS \"${expected}\")
  file(READ \"${expected}\" expected_output)
  string(REPLACE \"\\r\\n\" \"\\n\" expected_output \"\${expected_output}\")
endif()
if(output STREQUAL expected_output)
  file(REMOVE \"${actual}\")
else()
  file(WRITE \"${actual}\" \"\${output}\")
  execute_process(COMMAND \"${Python3_EXECUTABLE}\" -c \"${_VISUALIZER_TEST_DIFF}\"
                  \"${expected}\" \"${actual}\")
  if(EXISTS \"${expected}\")
    message(SEND_ERROR \"output differs from ${expected} (actual output: ${actual})\")
  else()
    message(SEND_ERROR \"expected output ${expected} is missing (actual output: ${actual})\")
  endif()
endif()
if(NOT result EQUAL 0)
  message(SEND_ERROR \"cxx-debug-visualize failed: \${result}\")
endif()
")

  set(debug_only "")
  if(_visualizer_test_multi_config)
    set(debug_only CONFIGURATIONS Debug)
  endif()
  add_test(NAME ${kind}.${name}
           COMMAND "${CMAKE_COMMAND}" "-Dprogram=$<TARGET_FILE:${name}>" -P "${script}"
           ${debug_only})
  set_tests_properties(${kind}.${name} PROPERTIES LABELS visualizers)
  # Report a missing visualizer file as "not run" instead of running the test.
  set_property(TEST ${kind}.${name} APPEND PROPERTY REQUIRED_FILES "${file}")
endfunction()
