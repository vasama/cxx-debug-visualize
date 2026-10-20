#include "cxx_debug_visualize.hpp"
#include "mylib/containers.hpp"

int main()
{
  // A string, shown as `address "text"`, with the address as "0x?" in the expected files.
  {
    mylib::string hello("hello");
    visualize(hello);
  }

  // A wildcard type ($T1 is mylib::string*), whose own value gdb formats unlike natvis.
  {
    mylib::string hello("hello");
    mylib::optional<mylib::string*> ptr(&hello);
    visualize(ptr);
  }

  return 0;
}
