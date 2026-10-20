#include "mylib/containers.h"
#include "test_visualizers.h"

// Checked with FileCheck against the output of `test_visualizers run`: every
// `check_visualizer(x);` line prints x and the children its visualizer
// produces, headed by "check_visualizer(x) at <file>:<line>".
//
// This test runs twice, with natvis/mylib.natvis and with
// printers/mylib_printers.py: CHECK lines apply to both, NATVIS and GDB lines
// only to the natvis and the gdb pretty-printer run.

int main() {
  mylib::Point p{3, -4};
  check_visualizer(p);
  // CHECK: check_visualizer(p) at test_containers.cpp:[[@LINE-1]]
  // CHECK-NEXT:   (3, -4) [mylib::Point]
  // NATVIS-NEXT:    x = 3 [int]
  // NATVIS-NEXT:    y = -4 [int]

  mylib::Vector<int> empty;
  mylib::Vector<int> v;
  for (int i = 1; i <= 3; ++i)
    v.push_back(i * 10);
  mylib::Vector<mylib::Point> points;
  points.push_back({1, 2});
  mylib::List<int> list;
  list.push_front(3);
  list.push_front(2);
  list.push_front(1);
  mylib::Optional<int> none;
  mylib::Optional<int> some(42);
  mylib::IntMap<int> map;
  map.insert(20, 200);
  map.insert(10, 100);
  map.insert(30, 300);

  check_visualizer(empty);
  // CHECK: check_visualizer(empty) at test_containers.cpp:[[@LINE-1]]
  // NATVIS-NEXT:   { size=0 } [mylib::Vector<int>]
  // GDB-NEXT:      size=0 [mylib::Vector<int>]
  // NATVIS-NEXT:     [size] = 0 [std::size_t]
  // NATVIS-NEXT:     [capacity] = 0 [std::size_t]
  // NATVIS-NEXT:     [Raw View] = {...}

  check_visualizer(v);
  // CHECK: check_visualizer(v) at test_containers.cpp:[[@LINE-1]]
  // NATVIS-NEXT:   { size=3 } [mylib::Vector<int>]
  // GDB-NEXT:      size=3 [mylib::Vector<int>]
  // NATVIS-NEXT:     [size] = 3 [std::size_t]
  // NATVIS-NEXT:     [capacity] = 4 [std::size_t]
  // CHECK-NEXT:      [0] = 10 [int]
  // CHECK-NEXT:      [1] = 20 [int]
  // CHECK-NEXT:      [2] = 30 [int]
  // NATVIS-NEXT:     [Raw View] = {...}

  check_visualizer(points);
  // CHECK: check_visualizer(points) at test_containers.cpp:[[@LINE-1]]
  // NATVIS-NEXT:   { size=1 } [mylib::Vector<mylib::Point>]
  // GDB-NEXT:      size=1 [mylib::Vector<mylib::Point>]
  // CHECK:           [0] = (1, 2) [mylib::Point]
  // NATVIS-NEXT:     [Raw View] = {...}

  check_visualizer(list);
  // CHECK: check_visualizer(list) at test_containers.cpp:[[@LINE-1]]
  // NATVIS-NEXT:   { size=3 } [mylib::List<int>]
  // GDB-NEXT:      size=3 [mylib::List<int>]
  // CHECK-NEXT:      [0] = 1 [int]
  // CHECK-NEXT:      [1] = 2 [int]
  // CHECK-NEXT:      [2] = 3 [int]
  // NATVIS-NEXT:     [Raw View] = {...}

  check_visualizer(none);
  // CHECK: check_visualizer(none) at test_containers.cpp:[[@LINE-1]]
  // CHECK-NEXT:   empty [mylib::Optional<int>]
  // NATVIS-NEXT:    [Raw View] = {...}

  check_visualizer(some);
  // CHECK: check_visualizer(some) at test_containers.cpp:[[@LINE-1]]
  // CHECK-NEXT:   42 [mylib::Optional<int>]
  // CHECK-NEXT:     [value] = 42 [int]
  // NATVIS-NEXT:    [Raw View] = {...}

  // MIEngine ignores TreeItems' ValueNode Name, so natvis children are [0],
  // [1], ...; gdb's "map" display hint names them by key.
  check_visualizer(map);
  // CHECK: check_visualizer(map) at test_containers.cpp:[[@LINE-1]]
  // NATVIS-NEXT:   { size=3 } [mylib::IntMap<int>]
  // NATVIS-NEXT:     [0] = 100 [int]
  // NATVIS-NEXT:     [1] = 200 [int]
  // NATVIS-NEXT:     [2] = 300 [int]
  // NATVIS-NEXT:     [Raw View] = {...}
  // GDB-NEXT:      size=3 [mylib::IntMap<int>]
  // GDB-NEXT:        [10] = 100 [int]
  // GDB-NEXT:        [20] = 200 [int]
  // GDB-NEXT:        [30] = 300 [int]

  // With natvis, elements past the first 50 are paged under a "[More...]"
  // node; gdb lists them all.
  mylib::Vector<int> big;
  for (int i = 0; i < 60; ++i)
    big.push_back(i);
  check_visualizer(big);
  // CHECK: check_visualizer(big) at test_containers.cpp:[[@LINE-1]]
  // NATVIS-NEXT:   { size=60 } [mylib::Vector<int>]
  // GDB-NEXT:      size=60 [mylib::Vector<int>]
  // CHECK:           [49] = 49 [int]
  // NATVIS-NEXT:     [More...] = {...}
  // CHECK-NEXT:        [50] = 50 [int]
  // CHECK:             [59] = 59 [int]
  // NATVIS-NEXT:     [Raw View] = {...}
  return 0;
}
