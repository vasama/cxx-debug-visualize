#include "mylib/containers.h"
#include "test_visualizers.h"

// Checks also work in other functions; references show the referee.
static void greet(const mylib::String &name) {
  check_visualizer(name);
}

int main() {
  // gdb prints char pointers as `address "text"`; match the address with a
  // regex.
  mylib::String hello("hello");
  check_visualizer(hello);
  // CHECK: check_visualizer(hello) at test_strings.cpp:[[@LINE-1]]
  // CHECK-NEXT:   {{0x[0-9a-f]+}} "hello" [mylib::String]
  // CHECK-NEXT:     [size] = 5 [std::size_t]

  mylib::String world("world");
  greet(world);
  // CHECK: check_visualizer(name) at test_strings.cpp:6
  // CHECK-NEXT:   {{0x[0-9a-f]+}} "world" [const mylib::String &]
  // CHECK-NEXT:     [size] = 5 [std::size_t]

  // Wildcard types: $T1 is mylib::String *.  Both visualizers show a pointer
  // with its target's visualizer, but gdb formats the optional's own value,
  // which is that pointer, in its own way.
  mylib::Optional<mylib::String *> ptr(&hello);
  check_visualizer(ptr);
  // CHECK: check_visualizer(ptr) at test_strings.cpp:[[@LINE-1]]
  // NATVIS-NEXT:   {{0x[0-9a-f]+}} "hello" [mylib::Optional<mylib::String*>]
  // GDB-NEXT:      "hello" = {[size] = 5} [mylib::Optional<mylib::String*>]
  // CHECK-NEXT:      [value] = {{0x[0-9a-f]+}} "hello" [mylib::String *]
  return 0;
}
