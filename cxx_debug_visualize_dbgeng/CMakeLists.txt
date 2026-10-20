# The DbgEng debug adapter (see main.cpp), Windows only. It needs the Windows SDK to build, and the
# Debugging Tools for Windows to run: it loads their dbgeng.dll.
cmake_minimum_required(VERSION 3.24)
project(dbgeng-adapter LANGUAGES CXX)

if(NOT WIN32)
  message(FATAL_ERROR "The DbgEng adapter can only be built for Windows")
endif()

add_executable(dbgeng-adapter engine.cpp main.cpp)
target_compile_features(dbgeng-adapter PRIVATE cxx_std_23)
# Without the min and max macros from windows.h, which break std::min and std::max.
target_compile_definitions(dbgeng-adapter PRIVATE NOMINMAX)
# nlohmann/json 3.12.0, whose single header is vendored in third_party/.
target_include_directories(dbgeng-adapter SYSTEM PRIVATE third_party)
target_link_libraries(dbgeng-adapter PRIVATE oleaut32)
