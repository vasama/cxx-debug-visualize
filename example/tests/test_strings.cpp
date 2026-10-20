#include "mylib/containers.h"
#include "natvistest.h"

// Checks also work in other functions; references show the referee.
static void greet(const mylib::String &name) {
  check_visualizer(name);
}

int main() {
  // gdb prints char pointers as `address "text"`; match the address with a regex.
  mylib::String hello("hello");
  check_visualizer(hello);
  // CHECK: check_visualizer(hello) at test_strings.cpp:[[@LINE-1]]
  // CHECK-NEXT:   {{0x[0-9a-f]+}} "hello" [mylib::String]
  // CHECK-NEXT:     [size] = 5 [std::size_t]
  // CHECK-NEXT:     [Raw View] = {...}

  mylib::String world("world");
  greet(world);
  // CHECK: check_visualizer(name) at test_strings.cpp:6
  // CHECK-NEXT:   {{0x[0-9a-f]+}} "world" [const mylib::String &]
  // CHECK-NEXT:     [size] = 5 [std::size_t]

  // Wildcard types: $T1 is mylib::String *
  mylib::Optional<mylib::String *> ptr(&hello);
  check_visualizer(ptr);
  // CHECK: check_visualizer(ptr) at test_strings.cpp:[[@LINE-1]]
  // CHECK-NEXT:   {{0x[0-9a-f]+}} "hello" [mylib::Optional<mylib::String*>]
  // CHECK-NEXT:     [value] = {{0x[0-9a-f]+}} "hello" [mylib::String *]
  // CHECK-NEXT:     [Raw View] = {...}
  return 0;
}
