# CTest integration for cxx-debug-visualize.
#
#   include(CxxDebugVisualize)
#   cxx_debug_visualize_add_test(<name>
#     SOURCES <test.cpp>...              # the first one is the test source
#     [NATVIS <file.natvis>]             # natvis file under test
#     [GDB_PRINTERS <printers.py>]       # gdb pretty-printer script under test
#     [LINK_LIBRARIES <lib>...]
#     [INCLUDE_DIRECTORIES <dir>...]
#     [ARGS <option>...]                 # cxx-debug-visualize options, e.g. --trace
#   )
#
# Builds <name> once, without optimizations and with debug info, and registers
# a CTest test for each visualizer given (at least one): "natvis.<name>" and
# "gdb.<name>", labelled "visualizers".  Each runs <name> under the VS Code
# C/C++ debug adapter and compares the printed Variables trees with an
# expected output file next to the test source, the first file in SOURCES:
# <test>.natvis.txt and <test>.gdb.txt for tests/<test>.cpp.  cxx-debug-visualize
# breaks on the test source's visualize() lines.
#
# Addresses differ between machines, so every hexadecimal number (0x...) in the
# output is replaced by "0x?" before comparing; expected files contain "0x?" in
# their place.  A test fails if cxx-debug-visualize fails or the output differs from the
# expected file (or that is missing).  The actual output is then written to
# <kind>.<name>.actual.txt in the build directory, for review or to copy over
# the expected file, and a diff is printed.
#
# Cache variable (required):
#   CXX_DEBUG_VISUALIZE_ADAPTER    path to OpenDebugAD7, passed as --adapter

find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)

# Prints a unified diff of an expected file (possibly missing) and the actual output.
set(_CXX_DEBUG_VISUALIZE_DIFF "import difflib, os, sys
expected, actual = sys.argv[1:]
old = open(expected).readlines() if os.path.exists(expected) else []
sys.stdout.writelines(difflib.unified_diff(old, open(actual).readlines(), expected, actual))")

get_filename_component(CXX_DEBUG_VISUALIZE_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
set(CXX_DEBUG_VISUALIZE_ADAPTER "" CACHE FILEPATH "Path to OpenDebugAD7")
if(NOT CXX_DEBUG_VISUALIZE_ADAPTER)
  message(FATAL_ERROR "CxxDebugVisualize: set CXX_DEBUG_VISUALIZE_ADAPTER to the path of "
                      "OpenDebugAD7, e.g. "
                      "-DCXX_DEBUG_VISUALIZE_ADAPTER=<cpptools>/debugAdapters/bin/OpenDebugAD7")
endif()

function(cxx_debug_visualize_add_test name)
  cmake_parse_arguments(PARSE_ARGV 1 TV "" "NATVIS;GDB_PRINTERS"
                        "SOURCES;LINK_LIBRARIES;INCLUDE_DIRECTORIES;ARGS")
  if(NOT TV_SOURCES)
    message(FATAL_ERROR "cxx_debug_visualize_add_test(${name}): SOURCES is required")
  endif()
  if(NOT TV_NATVIS AND NOT TV_GDB_PRINTERS)
    message(FATAL_ERROR "cxx_debug_visualize_add_test(${name}): NATVIS or GDB_PRINTERS is required")
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
    _cxx_debug_visualize_add_run(natvis ${name} "${test_source}" --natvis "${TV_NATVIS}" ${TV_ARGS})
  endif()
  if(TV_GDB_PRINTERS)
    _cxx_debug_visualize_add_run(gdb ${name} "${test_source}" --gdb-printers "${TV_GDB_PRINTERS}"
                         ${TV_ARGS})
  endif()
endfunction()

# Register the CTest test "<kind>.<name>", which runs the program <name> with
# the visualizer <option> <file> and compares the output with
# <test source>.<kind>.txt.  Further arguments are passed on to cxx-debug-visualize.
function(_cxx_debug_visualize_add_run kind name test_source option file)
  get_filename_component(file "${file}" ABSOLUTE)
  get_filename_component(test_dir "${test_source}" DIRECTORY)
  get_filename_component(test_name "${test_source}" NAME_WE)
  set(expected "${test_dir}/${test_name}.${kind}.txt")
  set(actual "${CMAKE_CURRENT_BINARY_DIR}/${kind}.${name}.actual.txt")
  set(run "${Python3_EXECUTABLE}" -m cxx_debug_visualize
      --adapter "${CXX_DEBUG_VISUALIZE_ADAPTER}" ${option} "${file}"
      ${ARGN} "${test_source}" "$<TARGET_FILE:${name}>")

  # A CTest test is a single command, so the comparison runs from a generated
  # script.
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
  execute_process(COMMAND \"${Python3_EXECUTABLE}\" -c \"${_CXX_DEBUG_VISUALIZE_DIFF}\"
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
  set_tests_properties(${kind}.${name} PROPERTIES
    ENVIRONMENT "PYTHONPATH=${CXX_DEBUG_VISUALIZE_ROOT}"
    LABELS visualizers)
  # Report a missing visualizer file as "not run" instead of running the test.
  set_property(TEST ${kind}.${name} APPEND PROPERTY REQUIRED_FILES "${file}")
endfunction()
