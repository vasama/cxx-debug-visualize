// Helper for natvis test programs.
//
// test_visualizers sets a breakpoint on every line that consists of exactly
// `check_visualizer(identifier);` and prints the Variables tree of that object
// each time the line runs.  It is a real call (not inlined away) that keeps
// the object alive.
#pragma once

#if defined(_MSC_VER)
#define TEST_VISUALIZERS_NOINLINE __declspec(noinline)
#else
#define TEST_VISUALIZERS_NOINLINE __attribute__((noinline))
#endif

template <typename T> TEST_VISUALIZERS_NOINLINE void check_visualizer(const T &) {
  // Prevent the call from being optimized out.
#if defined(__GNUC__) || defined(__clang__)
  asm volatile("" ::: "memory");
#endif
}
