// Fixture for the cxx-vistest integration self-tests (line numbers matter: the tests
// refer to check_visualizer() calls by line).  Build with -DCRASH=0|1.
#include "cxx_vistest.h"

struct Pair { int a; int b; };
struct Arr { int *data; int n; }; struct PairArr { Pair *data; int n; };

static void crash() {
  volatile int *p = nullptr;
  *p = 1;
}

int main() {
  Pair pr{1, 2};
  int storage[3] = {7, 8, 9};
  Arr arr{storage, 3};
  check_visualizer(pr);
  check_visualizer(arr);
  for (int i = 0; i < 2; ++i) {
    pr.a = i;
    check_visualizer(pr);
  }
  check_visualizer(pr); // not a breakpoint: the line holds more than the call
  Pair pairs[2] = {{3, 4}, {5, 6}};
  PairArr pa{pairs, 2};
  check_visualizer(pa);
  int many[120];
  for (int i = 0; i < 120; ++i)
    many[i] = i;
  Arr big{many, 120};
  check_visualizer(big);
  // every check_visualizer call above is reached before the optional crash
  if (CRASH)
    crash();
  return 0;
}
