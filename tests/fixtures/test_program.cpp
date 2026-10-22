// Fixture for the cxx-debug-visualize integration self-tests.
//
// An argument changes the program behaviour:
// -c causes the program to crash.
// -f causes the program to return 1.
#include "cxx_debug_visualize.hpp"

struct pair
{
  int a;
  int b;
};

struct int_array
{
  int* data;
  int n;
};

struct pair_array
{
  pair* data;
  int n;
};

// Visualizes an object through a reference, from outside main.
static void show(pair const& ref)
{
  visualize(ref);
}

int main(int argc, char** argv)
{
  if (argc != 1)
  {
    if (argc != 2)
      return 2;

    if (argv[1][0] != '-')
      return 2;

    char const option = argv[1][1];
    if (argv[1][2] != '\0')
      return 2;

    if (option != 'c' && option != 'f')
      return 2;

    if (option == 'c')
    {
      int volatile* volatile p = nullptr;
      *p = 0;
    }

    return 1;
  }

  // A type with only a display string.
  {
    pair pr{1, 2};
    visualize(pr);
  }

  // An array shown as its elements.
  {
    int storage[3] = {7, 8, 9};
    int_array arr{storage, 3};
    visualize(arr);
  }

  // A call in a loop, which prints once per iteration.
  {
    pair pr{1, 2};
    for (int i = 0; i < 2; ++i)
    {
      pr.a = i;
      visualize(pr);
    }
  }

  // A line holding more than the call, which is not a breakpoint.
  {
    pair pr{1, 2};
    visualize(pr); // not a breakpoint: the line holds more than the call
  }

  // An array of pairs, which the printers and formatters show as a map from a to b.
  {
    pair pairs[2] = {{3, 4}, {5, 6}};
    pair_array pa{pairs, 2};
    visualize(pa);
  }

  // More than 50 elements, which natvis pages under "[More...]".
  {
    int many[120];
    for (int i = 0; i < 120; ++i)
      many[i] = i;
    int_array big{many, 120};
    visualize(big);
  }

  // A call in another function, on a reference.
  {
    pair pr{1, 2};
    show(pr);
  }

  return 0;
}
