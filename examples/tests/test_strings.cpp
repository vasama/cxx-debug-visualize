#include "cxx_debug_visualize.hpp"
#include "mylib/containers.hpp"

// Checks also work in other functions; references show the referee.
static void greet(mylib::string const& name)
{
  visualize(name);
}

int main()
{
  // A string, shown as `address "text"`, with the address as "0x?" in the expected files.
  {
    mylib::string hello("hello");
    visualize(hello);
  }

  // A call in another function, on a reference.
  {
    mylib::string world("world");
    greet(world);
  }

  // A wildcard type ($T1 is mylib::string*), whose own value gdb formats unlike natvis.
  {
    mylib::string hello("hello");
    mylib::optional<mylib::string*> ptr(&hello);
    visualize(ptr);
  }

  return 0;
}
