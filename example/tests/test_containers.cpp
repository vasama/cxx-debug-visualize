#include "mylib/containers.h"
#include "cxx_vistest.h"

// Checked with FileCheck against the output of `cxx-vistest`: every
// `visualize(x);` line prints x and the children its visualizer
// produces, headed by "visualize(x) at <file>:<line>".
//
// This test runs twice, with natvis/mylib.natvis and with
// printers/mylib_printers.py.  The printers mirror the natvis file, so the
// same CHECK lines hold for both.

int main() {
  mylib::Point p{3, -4};
  visualize(p);
  // CHECK: visualize(p) at test_containers.cpp:[[@LINE-1]]
  // CHECK-NEXT:   (3, -4) [mylib::Point]
  // CHECK-NEXT:     x = 3 [int]
  // CHECK-NEXT:     y = -4 [int]

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

  visualize(empty);
  // CHECK: visualize(empty) at test_containers.cpp:[[@LINE-1]]
  // CHECK-NEXT:   { size=0 } [mylib::Vector<int>]
  // CHECK-NEXT:     [size] = 0 [std::size_t]
  // CHECK-NEXT:     [capacity] = 0 [std::size_t]

  visualize(v);
  // CHECK: visualize(v) at test_containers.cpp:[[@LINE-1]]
  // CHECK-NEXT:   { size=3 } [mylib::Vector<int>]
  // CHECK-NEXT:     [size] = 3 [std::size_t]
  // CHECK-NEXT:     [capacity] = 4 [std::size_t]
  // CHECK-NEXT:     [0] = 10 [int]
  // CHECK-NEXT:     [1] = 20 [int]
  // CHECK-NEXT:     [2] = 30 [int]

  visualize(points);
  // CHECK: visualize(points) at test_containers.cpp:[[@LINE-1]]
  // CHECK-NEXT:   { size=1 } [mylib::Vector<mylib::Point>]
  // CHECK:          [0] = (1, 2) [mylib::Point]

  visualize(list);
  // CHECK: visualize(list) at test_containers.cpp:[[@LINE-1]]
  // CHECK-NEXT:   { size=3 } [mylib::List<int>]
  // CHECK-NEXT:     [0] = 1 [int]
  // CHECK-NEXT:     [1] = 2 [int]
  // CHECK-NEXT:     [2] = 3 [int]

  visualize(none);
  // CHECK: visualize(none) at test_containers.cpp:[[@LINE-1]]
  // CHECK-NEXT:   empty [mylib::Optional<int>]

  visualize(some);
  // CHECK: visualize(some) at test_containers.cpp:[[@LINE-1]]
  // CHECK-NEXT:   42 [mylib::Optional<int>]
  // CHECK-NEXT:     [value] = 42 [int]

  // MIEngine ignores TreeItems' ValueNode Name, so natvis children are [0],
  // [1], ...; the printer names them the same way.
  visualize(map);
  // CHECK: visualize(map) at test_containers.cpp:[[@LINE-1]]
  // CHECK-NEXT:   { size=3 } [mylib::IntMap<int>]
  // CHECK-NEXT:     [0] = 100 [int]
  // CHECK-NEXT:     [1] = 200 [int]
  // CHECK-NEXT:     [2] = 300 [int]

  // natvis pages elements past the first 50 under a "[More...]" node, which
  // cxx-vistest flattens into the list.
  mylib::Vector<int> big;
  for (int i = 0; i < 60; ++i)
    big.push_back(i);
  visualize(big);
  // CHECK: visualize(big) at test_containers.cpp:[[@LINE-1]]
  // CHECK-NEXT:   { size=60 } [mylib::Vector<int>]
  // CHECK:          [49] = 49 [int]
  // CHECK-NEXT:     [50] = 50 [int]
  // CHECK:          [59] = 59 [int]
  return 0;
}
