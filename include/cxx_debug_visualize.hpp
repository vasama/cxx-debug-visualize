// SPDX-License-Identifier: MIT-0

#pragma once

// Helper for visualizer test programs.
//
// cxx-debug-visualize sets a breakpoint on every line that consists of exactly
// `visualize(identifier);` and prints the visualization of that object each
// time the breakpoint is hit.
//
// Note that the use of this header is not necessary. As long as the name
// matches and the line generates executable code, it is possible to define an
// equivalent function or even macro directly in visualizer test source.

#include <memory>

template<typename T>
#if defined(_MSC_VER)
__declspec(noinline)
#else
__attribute__((noinline))
#endif
void visualize(T const& object)
{
  [[maybe_unused]] void const* volatile ptr = std::addressof(object);
}
