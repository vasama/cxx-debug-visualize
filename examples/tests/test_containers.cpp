#include "cxx_debug_visualize.hpp"
#include "mylib/containers.hpp"

// Every `visualize(x);` line prints x and the children its visualizer
// produces, headed by "visualize(x) at <file>:<line>".  The output is compared
// with test_containers.<kind>.txt: natvis, gdb-vs, gdb-native, lldb-native.
//
// The test runs once per visualizer in visualizers/: mylib.natvis, and
// mylib_printers.py and mylib_formatters.py, which mirror it, so the expected
// files only differ where a debugger formats a value in its own way.

int main()
{
  mylib::point p{3, -4};
  visualize(p);

  mylib::vector<int> empty;
  mylib::vector<int> v;
  for (int i = 1; i <= 3; ++i)
    v.push_back(i * 10);
  mylib::vector<mylib::point> points;
  points.push_back({1, 2});
  mylib::list<int> list;
  list.push_front(3);
  list.push_front(2);
  list.push_front(1);
  mylib::optional<int> none;
  mylib::optional<int> some(42);
  mylib::int_map<int> map;
  map.insert(20, 200);
  map.insert(10, 100);
  map.insert(30, 300);

  visualize(empty);
  visualize(v);
  visualize(points);
  visualize(list);
  visualize(none);
  visualize(some);

  // MIEngine ignores TreeItems' ValueNode Name, so natvis children are [0],
  // [1], ...; the printer names them the same way.
  visualize(map);

  // natvis pages elements past the first 50 under a "[More...]" node, which
  // cxx-debug-visualize flattens into the list.
  mylib::vector<int> big;
  for (int i = 0; i < 60; ++i)
    big.push_back(i);
  visualize(big);
  return 0;
}
