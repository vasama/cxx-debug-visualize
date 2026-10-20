// Helper for visualizer test programs.
//
// cxx-vistest sets a breakpoint on every line that consists of exactly
// `visualize(identifier);` and prints the Variables tree of that object
// each time the line runs.  It is a real call (not inlined away) that keeps
// the object alive.
#pragma once

#if defined(_MSC_VER)
#define CXX_VISTEST_NOINLINE __declspec(noinline)
#else
#define CXX_VISTEST_NOINLINE __attribute__((noinline))
#endif

template <typename T> CXX_VISTEST_NOINLINE void visualize(const T &) {
  // Prevent the call from being optimized out.
#if defined(__GNUC__) || defined(__clang__)
  asm volatile("" ::: "memory");
#endif
}
