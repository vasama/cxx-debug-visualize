cmake_minimum_required(VERSION 3.15)
project(mylib_visualizers_example CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../cmake")
include(CxxDebugVisualize)
enable_testing()

add_library(mylib INTERFACE)
target_include_directories(mylib INTERFACE include)

set(MYLIB_NATVIS "${CMAKE_CURRENT_SOURCE_DIR}/natvis/mylib.natvis")
set(MYLIB_PRINTERS "${CMAKE_CURRENT_SOURCE_DIR}/printers/mylib_printers.py")
set(MYLIB_FORMATTERS "${CMAKE_CURRENT_SOURCE_DIR}/formatters/mylib_formatters.py")

cxx_debug_visualize_add_test(test_containers
  SOURCES tests/test_containers.cpp
  NATVIS ${MYLIB_NATVIS}
  GDB_PRINTERS ${MYLIB_PRINTERS}
  LLDB_FORMATTERS ${MYLIB_FORMATTERS}
  LINK_LIBRARIES mylib)

cxx_debug_visualize_add_test(test_strings
  SOURCES tests/test_strings.cpp
  NATVIS ${MYLIB_NATVIS}
  GDB_PRINTERS ${MYLIB_PRINTERS}
  LLDB_FORMATTERS ${MYLIB_FORMATTERS}
  LINK_LIBRARIES mylib)
