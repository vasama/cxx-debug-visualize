# CTest integration for cxx-vistest.
#
#   include(CxxVistest)
#   cxx_vistest_add_test(<name>
#     SOURCES <test.cpp>...              # the first one is the test source
#     [NATVIS <file.natvis>]             # natvis file under test
#     [PRINTERS <printers.py>]           # gdb pretty-printer script under test
#     [LINK_LIBRARIES <lib>...]
#     [INCLUDE_DIRECTORIES <dir>...]
#     [ARGS <cxx-vistest option>...]  # e.g. --trace
#   )
#
# Builds <name> once, without optimizations and with debug info, and registers
# a CTest test for each visualizer given (at least one): "natvis.<name>" and
# "gdb.<name>", labelled "visualizers".  Each runs <name> under the VS Code
# C/C++ debug adapter and pipes the printed Variables trees into FileCheck.
# The first file in SOURCES is the test source: cxx-vistest breaks on its
# check_visualizer() lines, and FileCheck reads its CHECK lines.  A test fails
# if either cxx-vistest or FileCheck fails.
#
# With both NATVIS and PRINTERS, lines where the two outputs differ use the
# FileCheck prefixes NATVIS and GDB instead of CHECK: the tests run FileCheck
# with --check-prefixes=CHECK,NATVIS and CHECK,GDB.  Either prefix may go
# unused, e.g. when both visualizers produce the same output.
#
# Cache variables (both required):
#   CXX_VISTEST_ADAPTER    path to OpenDebugAD7, passed as --adapter
#   CXX_VISTEST_FILECHECK  path to LLVM's FileCheck

find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)

get_filename_component(CXX_VISTEST_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
set(CXX_VISTEST_ADAPTER "" CACHE FILEPATH "Path to OpenDebugAD7")
if(NOT CXX_VISTEST_ADAPTER)
  message(FATAL_ERROR "CxxVistest: set CXX_VISTEST_ADAPTER to the path of "
                      "OpenDebugAD7, e.g. "
                      "-DCXX_VISTEST_ADAPTER=<cpptools>/debugAdapters/bin/OpenDebugAD7")
endif()
set(CXX_VISTEST_FILECHECK "" CACHE FILEPATH "Path to LLVM's FileCheck")
if(NOT CXX_VISTEST_FILECHECK)
  message(FATAL_ERROR "CxxVistest: set CXX_VISTEST_FILECHECK to the path of "
                      "FileCheck, e.g. "
                      "-DCXX_VISTEST_FILECHECK=/usr/lib/llvm-18/bin/FileCheck")
endif()

function(cxx_vistest_add_test name)
  cmake_parse_arguments(PARSE_ARGV 1 TV "" "NATVIS;PRINTERS"
                        "SOURCES;LINK_LIBRARIES;INCLUDE_DIRECTORIES;ARGS")
  if(NOT TV_SOURCES)
    message(FATAL_ERROR "cxx_vistest_add_test(${name}): SOURCES is required")
  endif()
  if(NOT TV_NATVIS AND NOT TV_PRINTERS)
    message(FATAL_ERROR "cxx_vistest_add_test(${name}): NATVIS or PRINTERS is required")
  endif()

  add_executable(${name} ${TV_SOURCES})
  target_include_directories(${name} PRIVATE "${CXX_VISTEST_ROOT}/include"
                             ${TV_INCLUDE_DIRECTORIES})
  if(TV_LINK_LIBRARIES)
    target_link_libraries(${name} PRIVATE ${TV_LINK_LIBRARIES})
  endif()
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${name} PRIVATE -O0 -g)
  endif()

  list(GET TV_SOURCES 0 test_source)
  get_filename_component(test_source "${test_source}" ABSOLUTE)

  # Only a test source checked against both visualizers needs their prefixes.
  set(natvis_prefixes "")
  set(printers_prefixes "")
  if(TV_NATVIS AND TV_PRINTERS)
    set(natvis_prefixes --allow-unused-prefixes --check-prefixes=CHECK,NATVIS)
    set(printers_prefixes --allow-unused-prefixes --check-prefixes=CHECK,GDB)
  endif()
  if(TV_NATVIS)
    _cxx_vistest_add_run(natvis ${name} "${test_source}" --natvis "${TV_NATVIS}"
                              "${natvis_prefixes}" ${TV_ARGS})
  endif()
  if(TV_PRINTERS)
    _cxx_vistest_add_run(gdb ${name} "${test_source}" --printers "${TV_PRINTERS}"
                              "${printers_prefixes}" ${TV_ARGS})
  endif()
endfunction()

# Register the CTest test "<kind>.<name>", which runs the program <name> with
# the visualizer <option> <file> and FileCheck with <prefixes> (may be empty).
# Further arguments are passed on to cxx-vistest.
function(_cxx_vistest_add_run kind name test_source option file prefixes)
  get_filename_component(file "${file}" ABSOLUTE)
  set(run "${Python3_EXECUTABLE}" -m cxx_vistest
      --adapter "${CXX_VISTEST_ADAPTER}" ${option} "${file}"
      ${ARGN} "${test_source}" "$<TARGET_FILE:${name}>")
  set(filecheck "${CXX_VISTEST_FILECHECK}")
  if(prefixes)
    list(APPEND filecheck "${prefixes}")
  endif()
  list(APPEND filecheck "${test_source}")

  # A CTest test is a single command, so the pipeline runs from a generated
  # script, which checks the exit codes of both processes.
  set(run_quoted "")
  foreach(arg IN LISTS run)
    string(APPEND run_quoted " \"${arg}\"")
  endforeach()
  set(filecheck_quoted "")
  foreach(arg IN LISTS filecheck)
    string(APPEND filecheck_quoted " \"${arg}\"")
  endforeach()
  set(script "${CMAKE_CURRENT_BINARY_DIR}/${kind}-${name}.cmake")
  file(GENERATE OUTPUT "${script}" CONTENT
"execute_process(
  COMMAND${run_quoted}
  COMMAND${filecheck_quoted}
  RESULTS_VARIABLE results)
if(NOT results STREQUAL \"0;0\")
  message(FATAL_ERROR \"cxx-vistest / FileCheck exit codes: \${results}\")
endif()
")

  add_test(NAME ${kind}.${name} COMMAND "${CMAKE_COMMAND}" -P "${script}")
  set_tests_properties(${kind}.${name} PROPERTIES
    ENVIRONMENT "PYTHONPATH=${CXX_VISTEST_ROOT}"
    LABELS visualizers)
  # Report a missing visualizer file as "not run" instead of running the test.
  set_property(TEST ${kind}.${name} APPEND PROPERTY REQUIRED_FILES "${file}")
endfunction()
