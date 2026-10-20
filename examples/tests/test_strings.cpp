#include "cxx_debug_visualize.hpp"
#include "mylib/containers.hpp"

// Checks also work in other functions; references show the referee.
static void greet(mylib::string const& name)
{
  visualize(name);
}

int main()
{
  // gdb prints char pointers as `address "text"`; the address shows as "0x?"
  // in the expected files.
  mylib::string hello("hello");
  visualize(hello);

  mylib::string world("world");
  greet(world);

  // Wildcard types: $T1 is mylib::string *.  Both visualizers show a pointer
  // with its target's visualizer, but gdb formats the optional's own value,
  // which is that pointer, in its own way, so the expected files differ here.
  mylib::optional<mylib::string*> ptr(&hello);
  visualize(ptr);
  return 0;
}
