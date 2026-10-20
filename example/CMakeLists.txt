cmake_minimum_required(VERSION 3.15)
project(mylib_visualizers_example LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/ExpectedOutputTests.cmake")
enable_testing()

add_library(mylib INTERFACE)
target_include_directories(mylib INTERFACE include)

set(MYLIB_NATVIS "${CMAKE_CURRENT_SOURCE_DIR}/visualizers/mylib.natvis")
set(MYLIB_PRINTERS "${CMAKE_CURRENT_SOURCE_DIR}/visualizers/mylib_printers.py")
set(MYLIB_FORMATTERS "${CMAKE_CURRENT_SOURCE_DIR}/visualizers/mylib_formatters.py")

add_visualizer_test(
  test_containers
    SOURCES tests/test_containers.cpp
    NATVIS ${MYLIB_NATVIS}
    GDB_PRINTERS ${MYLIB_PRINTERS}
    LLDB_FORMATTERS ${MYLIB_FORMATTERS}
    LINK_LIBRARIES mylib
)

add_visualizer_test(
  test_strings
    SOURCES tests/test_strings.cpp
    NATVIS ${MYLIB_NATVIS}
    GDB_PRINTERS ${MYLIB_PRINTERS}
    LLDB_FORMATTERS ${MYLIB_FORMATTERS}
    LINK_LIBRARIES mylib
)
