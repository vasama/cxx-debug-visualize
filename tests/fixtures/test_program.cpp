// Fixture for the cxx-debug-visualize integration self-tests (line numbers matter: the tests
// refer to visualize() calls by line).  Crashes at the end if given any argument.
#include "cxx_debug_visualize.hpp"

struct pair { int a; int b; };
struct int_array { int *data; int n; }; struct pair_array { pair *data; int n; };

static void crash() {
  volatile int *p = nullptr;
  *p = 1;
}

int main(int argc, char **) {
  pair pr{1, 2};
  int storage[3] = {7, 8, 9};
  int_array arr{storage, 3};
  visualize(pr);
  visualize(arr);
  for (int i = 0; i < 2; ++i) {
    pr.a = i;
    visualize(pr);
  }
  visualize(pr); // not a breakpoint: the line holds more than the call
  pair pairs[2] = {{3, 4}, {5, 6}};
  pair_array pa{pairs, 2};
  visualize(pa);
  int many[120];
  for (int i = 0; i < 120; ++i)
    many[i] = i;
  int_array big{many, 120};
  visualize(big);
  // every visualize call above is reached before the optional crash
  if (argc > 1)
    crash();
  return 0;
}
