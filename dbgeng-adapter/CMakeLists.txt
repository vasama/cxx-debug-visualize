# The DbgEng debug adapter (see main.cpp), Windows only. It needs the Windows SDK to build, and the
# Debugging Tools for Windows to run: it loads their dbgeng.dll.
cmake_minimum_required(VERSION 3.24)
project(dbgeng-adapter LANGUAGES CXX)

if(NOT WIN32)
  message(FATAL_ERROR "The DbgEng adapter can only be built for Windows")
endif()

# nlohmann/json: an installed package if there is one (e.g. from vcpkg), else downloaded.
include(FetchContent)
FetchContent_Declare(
  nlohmann_json
  URL https://github.com/nlohmann/json/releases/download/v3.12.0/json.tar.xz
  URL_HASH SHA256=42f6e95cad6ec532fd372391373363b62a14af6d771056dbfc86160e6dfff7aa
  FIND_PACKAGE_ARGS 3.12)
FetchContent_MakeAvailable(nlohmann_json)

add_executable(dbgeng-adapter engine.cpp main.cpp)
target_compile_features(dbgeng-adapter PRIVATE cxx_std_23)
# Without the min and max macros from windows.h, which break std::min and std::max.
target_compile_definitions(dbgeng-adapter PRIVATE NOMINMAX)
target_link_libraries(dbgeng-adapter PRIVATE nlohmann_json::nlohmann_json oleaut32)
