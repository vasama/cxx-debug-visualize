# Finds the Windows debug engine (DbgEng) for the target architecture: its headers (DbgModel.h,
# dbgeng.h) and dbgeng.dll. By default they are those of the Debugging Tools for Windows. DbgEng_ROOT
# (a CMake or environment variable) may name another installation, such as an extracted
# Microsoft.Debugging.Platform.DbgEng NuGet package, which is searched first.
#
# Result variables:
#   DbgEng_FOUND        whether both were found
#   DbgEng_INCLUDE_DIR  the directory of the headers
#   DbgEng_DLL          dbgeng.dll; the DLLs it loads (dbgmodel.dll, dbghelp.dll) are next to it

# The directories of dbgeng.dll in the Debugging Tools (e.g. x64) and in the package (content/amd64).
string(TOLOWER "${CMAKE_CXX_COMPILER_ARCHITECTURE_ID}" _dbgeng_arch)
if(_dbgeng_arch STREQUAL "x64")
  set(_dbgeng_dll_suffixes x64 content/amd64)
elseif(_dbgeng_arch STREQUAL "arm64" OR _dbgeng_arch STREQUAL "x86")
  set(_dbgeng_dll_suffixes ${_dbgeng_arch} content/${_dbgeng_arch})
endif()

# DbgEng_ROOT is given as a hint, as CMake would only search its include/ directory.
set(_dbgeng_program_files "ProgramFiles(x86)")
set(_dbgeng_hints ${DbgEng_ROOT} $ENV{DbgEng_ROOT}
                  "$ENV{${_dbgeng_program_files}}/Windows Kits/10/Debuggers")

# Not the headers of the Windows SDK (INCLUDE), nor the older dbgeng.dll in System32 (PATH). The
# file names are matched ignoring case, as the Debugging Tools' header is DbgModel.h.
find_path(DbgEng_INCLUDE_DIR
          NAMES dbgmodel.h
          HINTS ${_dbgeng_hints}
          PATH_SUFFIXES inc build/native/inc
          NO_SYSTEM_ENVIRONMENT_PATH
          NO_CMAKE_SYSTEM_PATH)
if(_dbgeng_dll_suffixes)
  find_file(DbgEng_DLL
            NAMES dbgeng.dll
            HINTS ${_dbgeng_hints}
            PATH_SUFFIXES ${_dbgeng_dll_suffixes}
            NO_SYSTEM_ENVIRONMENT_PATH
            NO_CMAKE_SYSTEM_PATH)
endif()

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(DbgEng REQUIRED_VARS DbgEng_INCLUDE_DIR DbgEng_DLL)
