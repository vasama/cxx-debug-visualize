# The DbgEng debug adapter (see main.cpp), Windows only. It needs a compiler for the MSVC ABI
# (MSVC, or Clang targeting MSVC, including clang-cl), the Windows SDK, and the Windows debug engine
# (DbgEng): its headers to build, and its dbgeng.dll, which it loads, to run. They are those of the
# Debugging Tools for Windows, unless DbgEng_ROOT names others (see cmake/FindDbgEng.cmake).
cmake_minimum_required(VERSION 3.24)
project(dbgeng-adapter LANGUAGES CXX)

# It relies on Microsoft's C++ extensions, such as __uuidof on DbgEng's interfaces.
if(NOT (CMAKE_CXX_COMPILER_ID STREQUAL "MSVC" OR CMAKE_CXX_SIMULATE_ID STREQUAL "MSVC"))
  message(FATAL_ERROR "The DbgEng adapter can only be built with MSVC, or Clang targeting MSVC")
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
find_package(DbgEng REQUIRED)

add_executable(dbgeng-adapter engine.cpp main.cpp)
target_compile_features(dbgeng-adapter PRIVATE cxx_std_23)
# Without the min and max macros from windows.h, which break std::min and std::max, nor the
# warnings that the C runtime's standard functions are unsafe (e.g. getenv and fopen).
target_compile_definitions(dbgeng-adapter PRIVATE NOMINMAX _CRT_SECURE_NO_WARNINGS)
# DbgEng's headers, and those of nlohmann/json 3.12.0, whose single header is vendored in
# third_party/.
target_include_directories(dbgeng-adapter SYSTEM PRIVATE "${DbgEng_INCLUDE_DIR}" third_party)
target_link_libraries(dbgeng-adapter PRIVATE oleaut32)
