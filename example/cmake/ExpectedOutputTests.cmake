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
# Builds the program <name> without optimizations and with debug info, so that each
# `visualize(x);` line compiles to code of its own, and with the repository's include/ directory,
# for cxx_debug_visualize.hpp. Registers CTest tests labelled
# "visualizers", which run <name> under cxx-debug-visualize:
#   natvis.<name>       NATVIS, through the VS Code C/C++ debug adapter (OpenDebugAD7)
#   gdb-adapter.<name>  GDB_PRINTERS, through OpenDebugAD7
#   gdb-native.<name>   GDB_PRINTERS, through gdb's own DAP support (GDB 14 and later)
#   lldb-native.<name>  LLDB_FORMATTERS, through lldb-dap (lldb-vscode before LLVM 18),
#                       which must be on PATH when the tests run
# Each compares the printed Variables trees with an expected output file next to the test
# source, the first file in SOURCES: <test>.<kind>.txt, e.g. <test>.natvis.txt,
# <test>.gdb-adapter.txt, <test>.gdb-native.txt and <test>.lldb-native.txt for tests/<test>.cpp.
#
# Addresses differ between machines, so every hexadecimal number (0x...) in the output is
# replaced by "0x?" before comparing; expected files contain "0x?" in their place.  A test fails
# if cxx-debug-visualize fails or the output differs from the expected file (or that is missing).
# The actual output is then written to <kind>.<name>.actual.txt in the build directory, for
# review or to copy over the expected file, and a diff is printed.
#
# Cache variables:
#   CXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER  path to OpenDebugAD7, passed as --vs-code-adapter to the
#                                        natvis and gdb-adapter tests (the native tests use no
#                                        adapter). Without it, those tests are registered
#                                        disabled, which CTest reports as "Not Run (Disabled)".
#   CXX_DEBUG_VISUALIZE_FAIL_ON_SKIP     make a missing CXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER an
#                                        error instead (default: OFF)

find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)

get_filename_component(CXX_DEBUG_VISUALIZE_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
set(CXX_DEBUG_VISUALIZE_COMMAND
    "${CMAKE_COMMAND}" -E env "PYTHONPATH=${CXX_DEBUG_VISUALIZE_ROOT}"
    "${Python3_EXECUTABLE}" -m cxx_debug_visualize)

set(CXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER "" CACHE FILEPATH "Path to OpenDebugAD7")
option(CXX_DEBUG_VISUALIZE_FAIL_ON_SKIP "Fail instead of skipping tests that cannot run" OFF)

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
  if((TV_NATVIS OR TV_GDB_PRINTERS) AND NOT CXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER
     AND CXX_DEBUG_VISUALIZE_FAIL_ON_SKIP)
    message(FATAL_ERROR "add_visualizer_test(${name}): set "
                        "CXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER to the path of OpenDebugAD7, e.g. "
                        "-DCXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER="
                        "<cpptools>/debugAdapters/bin/OpenDebugAD7")
  endif()

  add_executable(${name} ${TV_SOURCES})
  target_include_directories(${name} PRIVATE "${CXX_DEBUG_VISUALIZE_ROOT}/include"
                             ${TV_INCLUDE_DIRECTORIES})
  if(TV_LINK_LIBRARIES)
    target_link_libraries(${name} PRIVATE ${TV_LINK_LIBRARIES})
  endif()
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${name} PRIVATE -O0 -g)
  endif()

  list(GET TV_SOURCES 0 test_source)
  get_filename_component(test_source "${test_source}" ABSOLUTE)

  if(TV_NATVIS)
    _add_visualizer_run(natvis ${name} "${test_source}" vs-code
                        --natvis "${TV_NATVIS}" ${TV_ARGS})
  endif()
  if(TV_GDB_PRINTERS)
    _add_visualizer_run(gdb-adapter ${name} "${test_source}" vs-code
                        --gdb-printers "${TV_GDB_PRINTERS}" ${TV_ARGS})
    _add_visualizer_run(gdb-native ${name} "${test_source}" native
                        --gdb-printers "${TV_GDB_PRINTERS}" ${TV_ARGS})
  endif()
  if(TV_LLDB_FORMATTERS)
    _add_visualizer_run(lldb-native ${name} "${test_source}" native
                        --lldb-formatters "${TV_LLDB_FORMATTERS}" --debugger lldb ${TV_ARGS})
  endif()

  # The natvis and gdb-adapter tests need OpenDebugAD7; without it, they never run.
  if(NOT CXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER)
    foreach(kind IN ITEMS natvis gdb-adapter)
      if(TEST ${kind}.${name})
        set_tests_properties(${kind}.${name} PROPERTIES DISABLED TRUE)
      endif()
    endforeach()
  endif()
endfunction()

# Register the CTest test "<kind>.<name>", which runs the program <name> with --adapter <adapter>
# (native or vs-code) and the visualizer <option> <file>, and compares the output with
# <test source>.<kind>.txt.  Further arguments are passed on to cxx-debug-visualize.
function(_add_visualizer_run kind name test_source adapter option file)
  get_filename_component(file "${file}" ABSOLUTE)
  get_filename_component(test_dir "${test_source}" DIRECTORY)
  get_filename_component(test_name "${test_source}" NAME_WE)
  set(expected "${test_dir}/${test_name}.${kind}.txt")
  set(actual "${CMAKE_CURRENT_BINARY_DIR}/${kind}.${name}.actual.txt")
  set(run ${CXX_DEBUG_VISUALIZE_COMMAND} --adapter ${adapter})
  if(adapter STREQUAL "vs-code")
    list(APPEND run --vs-code-adapter "${CXX_DEBUG_VISUALIZE_VS_CODE_ADAPTER}")
  endif()
  list(APPEND run ${option} "${file}" ${ARGN} "${test_source}" "$<TARGET_FILE:${name}>")

  # A CTest test is a single command, so the comparison runs from a generated script.
  set(run_quoted "")
  foreach(arg IN LISTS run)
    string(APPEND run_quoted " \"${arg}\"")
  endforeach()
  set(script "${CMAKE_CURRENT_BINARY_DIR}/${kind}-${name}.cmake")
  file(GENERATE OUTPUT "${script}" CONTENT
"execute_process(
  COMMAND${run_quoted}
  OUTPUT_VARIABLE output
  RESULT_VARIABLE result)
string(REGEX REPLACE \"0x[0-9a-fA-F]+\" \"0x?\" output \"\${output}\")
set(expected_output \"\")
if(EXISTS \"${expected}\")
  file(READ \"${expected}\" expected_output)
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

  add_test(NAME ${kind}.${name} COMMAND "${CMAKE_COMMAND}" -P "${script}")
  set_tests_properties(${kind}.${name} PROPERTIES LABELS visualizers)
  # Report a missing visualizer file as "not run" instead of running the test.
  set_property(TEST ${kind}.${name} APPEND PROPERTY REQUIRED_FILES "${file}")
endfunction()
