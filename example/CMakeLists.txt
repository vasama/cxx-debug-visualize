cmake_minimum_required(VERSION 3.16)
project(mylib_natvis_example CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../cmake")
include(NatvisTest)
enable_testing()

add_library(mylib INTERFACE)
target_include_directories(mylib INTERFACE include)

set(MYLIB_NATVIS "${CMAKE_CURRENT_SOURCE_DIR}/natvis/mylib.natvis")

natvis_add_test(test_containers
  SOURCES tests/test_containers.cpp
  NATVIS ${MYLIB_NATVIS}
  LINK_LIBRARIES mylib)

natvis_add_test(test_strings
  SOURCES tests/test_strings.cpp
  NATVIS ${MYLIB_NATVIS}
  LINK_LIBRARIES mylib)
