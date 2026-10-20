#pragma once

// Helper for visualizer test programs.
//
// cxx-vistest sets a breakpoint on every line that consists of exactly
// `visualize(identifier);` and prints the visualization of that object each
// time the line is executed.
//
// Note that the use of this header is not necessary. As long as the name
// matches, it is possible to define an equivalent function directly in a
// visualizer unit test file.

#if defined(_MSC_VER)
#define CXX_VISTEST_NOINLINE __declspec(noinline)
#else
#define CXX_VISTEST_NOINLINE __attribute__((noinline))
#endif

template<typename T>
CXX_VISTEST_NOINLINE void visualize(T const&)
{
}
