#include "mylib/containers.h"
#include "test_visualizers.h"

// Checks also work in other functions; references show the referee.
static void greet(const mylib::String &name) {
  check_visualizer(name);
}

int main() {
  // With natvis, gdb prints char pointers as `address "text"`; match the
  // address with a regex.  The gdb printer shows just the text.
  mylib::String hello("hello");
  check_visualizer(hello);
  // CHECK: check_visualizer(hello) at test_strings.cpp:[[@LINE-1]]
  // NATVIS-NEXT:   {{0x[0-9a-f]+}} "hello" [mylib::String]
  // GDB-NEXT:      "hello" [mylib::String]
  // NATVIS-NEXT:     [size] = 5 [std::size_t]
  // NATVIS-NEXT:     [Raw View] = {...}

  mylib::String world("world");
  greet(world);
  // CHECK: check_visualizer(name) at test_strings.cpp:6
  // NATVIS-NEXT:   {{0x[0-9a-f]+}} "world" [const mylib::String &]
  // GDB-NEXT:      "world" [const mylib::String &]
  // NATVIS-NEXT:     [size] = 5 [std::size_t]

  // Wildcard types: $T1 is mylib::String *.  natvis shows a pointer with its
  // target's visualizer; gdb prints the pointer itself.
  mylib::Optional<mylib::String *> ptr(&hello);
  check_visualizer(ptr);
  // CHECK: check_visualizer(ptr) at test_strings.cpp:[[@LINE-1]]
  // NATVIS-NEXT:   {{0x[0-9a-f]+}} "hello" [mylib::Optional<mylib::String*>]
  // NATVIS-NEXT:     [value] = {{0x[0-9a-f]+}} "hello" [mylib::String *]
  // NATVIS-NEXT:     [Raw View] = {...}
  // GDB-NEXT:      {{0x[0-9a-f]+}} [mylib::Optional<mylib::String*>]
  // GDB-NEXT:        [value] = {{0x[0-9a-f]+}} [mylib::String *]
  return 0;
}
