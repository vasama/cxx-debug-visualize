#include "cxx_debug_visualize.hpp"
#include "mylib/containers.hpp"

// natvis CustomListItems: loops over a data structure with local variables, as Visual Studio
// evaluates them. MIEngine supports them with microsoft/MIEngine#1580. The output is compared with
// test_custom_list.natvis.txt.

int main()
{
  // Keys 1, 5 and 9 share bucket 1, key 2 is in bucket 2, and buckets 0 and 3 are empty.
  {
    mylib::hash_map<int> map(4);
    map.insert(1, 10);
    map.insert(5, 50);
    map.insert(2, 20);
    map.insert(9, 90);
    visualize(map);
  }

  // A hash map with only empty buckets.
  {
    mylib::hash_map<int> empty_map(4);
    visualize(empty_map);
  }

  // Two integers, a real and an empty entry, each shown by its own branch of If/Elseif/Else.
  {
    mylib::variant_array values(8);
    values.push_back(1);
    values.push_back(2.5);
    values.push_back_none();
    values.push_back(-3);
    visualize(values);
  }

  // An array without entries, which the Condition on CustomListItems leaves unexpanded.
  {
    mylib::variant_array empty_values(4);
    visualize(empty_values);
  }

  // More than 50 entries, which MIEngine pages under "[More...]".
  {
    mylib::variant_array many(60);
    for (int i = 0; i < 60; ++i)
      many.push_back(100 + i);
    visualize(many);
  }

  return 0;
}
