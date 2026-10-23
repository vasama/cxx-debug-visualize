#include "cxx_debug_visualize.hpp"
#include "mylib/containers.hpp"

int main()
{
  // A type with only a display string, whose members are its children.
  {
    mylib::point p{3, -4};
    visualize(p);
  }

  // An empty vector.
  {
    mylib::vector<int> empty;
    visualize(empty);
  }

  // A vector's size, capacity and elements.
  {
    mylib::vector<int> v;
    for (int i = 1; i <= 3; ++i)
      v.push_back(i * 10);
    visualize(v);
  }

  // A vector whose elements have a visualizer of their own.
  {
    mylib::vector<mylib::point> points;
    points.push_back({1, 2});
    visualize(points);
  }

  // A linked list.
  {
    mylib::list<int> list;
    list.push_front(3);
    list.push_front(2);
    list.push_front(1);
    visualize(list);
  }

  // An empty optional.
  {
    mylib::optional<int> none;
    visualize(none);
  }

  // An optional with a value.
  {
    mylib::optional<int> some(42);
    visualize(some);
  }

  // A tree, whose children are named [0], [1], ... as MIEngine ignores TreeItems' ValueNode Name.
  {
    mylib::int_map<int> map;
    map.insert(20, 200);
    map.insert(10, 100);
    map.insert(30, 300);
    visualize(map);
  }

  // More than 50 elements, which natvis pages under "[More...]" and cxx-debug-visualize flattens.
  {
    mylib::vector<int> big;
    for (int i = 0; i < 60; ++i)
      big.push_back(100 + i);
    visualize(big);
  }

  return 0;
}
