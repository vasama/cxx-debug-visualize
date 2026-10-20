# CTest integration for natvistest.
#
#   include(NatvisTest)
#   natvis_add_test(<name>
#     SOURCES <test.cpp>...            # the first one is the test source
#     NATVIS <file.natvis>             # the natvis file under test
#     [LINK_LIBRARIES <lib>...]
#     [INCLUDE_DIRECTORIES <dir>...]
#     [ARGS <natvistest run option>...]  # e.g. --trace
#   )
#
# Builds <name> without optimizations and with debug info, and registers a
# CTest test "natvis.<name>" that runs it under the VS Code C/C++ debug adapter
# and pipes the printed Variables trees into FileCheck.  The first file in
# SOURCES is the test source: natvistest breaks on its check_visualizer()
# lines, and FileCheck reads its CHECK lines.  The test fails if either
# natvistest or FileCheck fails.
#
# Cache variables (both required):
#   NATVISTEST_ADAPTER    path to OpenDebugAD7, passed as --adapter
#   NATVISTEST_FILECHECK  path to LLVM's FileCheck

find_package(Python3 3.8 REQUIRED COMPONENTS Interpreter)

get_filename_component(NATVISTEST_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
set(NATVISTEST_ADAPTER "" CACHE FILEPATH "Path to OpenDebugAD7")
if(NOT NATVISTEST_ADAPTER)
  message(FATAL_ERROR "NatvisTest: set NATVISTEST_ADAPTER to the path of OpenDebugAD7, "
                      "e.g. -DNATVISTEST_ADAPTER=<cpptools>/debugAdapters/bin/OpenDebugAD7")
endif()
set(NATVISTEST_FILECHECK "" CACHE FILEPATH "Path to LLVM's FileCheck")
if(NOT NATVISTEST_FILECHECK)
  message(FATAL_ERROR "NatvisTest: set NATVISTEST_FILECHECK to the path of FileCheck, "
                      "e.g. -DNATVISTEST_FILECHECK=/usr/lib/llvm-18/bin/FileCheck")
endif()

function(natvis_add_test name)
  cmake_parse_arguments(PARSE_ARGV 1 NT "" "NATVIS"
                        "SOURCES;LINK_LIBRARIES;INCLUDE_DIRECTORIES;ARGS")
  if(NOT NT_SOURCES)
    message(FATAL_ERROR "natvis_add_test(${name}): SOURCES is required")
  endif()
  if(NOT NT_NATVIS)
    message(FATAL_ERROR "natvis_add_test(${name}): NATVIS is required")
  endif()

  add_executable(${name} ${NT_SOURCES})
  target_include_directories(${name} PRIVATE "${NATVISTEST_ROOT}/include" ${NT_INCLUDE_DIRECTORIES})
  if(NT_LINK_LIBRARIES)
    target_link_libraries(${name} PRIVATE ${NT_LINK_LIBRARIES})
  endif()
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${name} PRIVATE -O0 -g)
  endif()

  list(GET NT_SOURCES 0 test_source)
  get_filename_component(test_source "${test_source}" ABSOLUTE)
  get_filename_component(natvis "${NT_NATVIS}" ABSOLUTE)
  set(run "${Python3_EXECUTABLE}" -m natvistest run --adapter "${NATVISTEST_ADAPTER}"
      --natvis "${natvis}")
  list(APPEND run ${NT_ARGS} "${test_source}" "$<TARGET_FILE:${name}>")

  # A CTest test is a single command, so the pipeline runs from a generated
  # script, which checks the exit codes of both processes.
  set(quoted "")
  foreach(arg IN LISTS run)
    string(APPEND quoted " \"${arg}\"")
  endforeach()
  set(script "${CMAKE_CURRENT_BINARY_DIR}/natvis-${name}.cmake")
  file(GENERATE OUTPUT "${script}" CONTENT
"execute_process(
  COMMAND${quoted}
  COMMAND \"${NATVISTEST_FILECHECK}\" \"${test_source}\"
  RESULTS_VARIABLE results)
if(NOT results STREQUAL \"0;0\")
  message(FATAL_ERROR \"natvistest / FileCheck exit codes: \${results}\")
endif()
")

  add_test(NAME natvis.${name} COMMAND "${CMAKE_COMMAND}" -P "${script}")
  set_tests_properties(natvis.${name} PROPERTIES
    ENVIRONMENT "PYTHONPATH=${NATVISTEST_ROOT}"
    LABELS natvis)
  # Report a missing natvis file as "not run" instead of running the test.
  set_property(TEST natvis.${name} APPEND PROPERTY REQUIRED_FILES "${natvis}")
endfunction()
