// Fixture for testing the standard library visualizers that debuggers ship: one object of each
// C++17 standard type that libstdc++'s or libc++'s gdb pretty printers, lldb's formatters (for
// libstdc++, libc++ and MSVC's STL) or MSVC's STL.natvis visualize, as of GCC 14, LLVM 23 and the
// MSVC STL of 2026. Build it as C++17.
//
// Left out: types that C++20 and later add, types that C++17 and C++20 removed (auto_ptr,
// binder1st, binder2nd, mem_fun_t and relatives, pointer_to_unary_function,
// pointer_to_binary_function, unary_negate, binary_negate), and extensions and technical
// specifications (__gnu_cxx::slist, std::tr1, std::experimental). Types internal to a library,
// such as its iterators, are visualized through the standard types that use them.
//
// Nor are the objects visualized whose libstdc++ gdb pretty printers fail without libstdc++'s own
// debug symbols: std::locale, std::stringbuf and the string streams, whose types are complete only
// in those; nor node handles, whose printer looks for a member that they lack (as of GCC 14); nor,
// with those printers, a map's end iterator, which they show as an element read from the memory
// around the map, which differs between runs.
//
// With STL.natvis, as the Debugging Tools for Windows ship it and DbgEng applies it, the objects
// whose visualizers do not work are not visualized either:
// * those that the Debugging Tools' copy, being older than MSVC's STL, shows wrongly: move
//   iterators (a member since renamed), system_clock::time_point (no visualizer yet) and a
//   vector's end iterator (shown as the memory past the vector);
// * those that STL.natvis shows wrongly: the end iterators of lists, unordered containers,
//   vector<bool> and reverse iterators (shown as the memory around them), string views of
//   char16_t and char32_t (shown as their first character), and Boyer-Moore searchers (shown as
//   an address);
// * those whose visualizers use what DbgEng does not support: views (shared_ptr, weak_ptr and the
//   unordered containers), function calls (exceptions, error_code and error_category), a custom
//   visualizer (exception_ptr) and the dynamic type of an object (function);
// * those that DbgEng fails to visualize: deque iterators, and any, of which it leaves out the
//   items named like intrinsics of its visualizer.
// Those that no other visualizers support are left out altogether: move iterators, a reverse
// iterator's end, Boyer-Moore searchers, exceptions, exception_ptr and error_category.
//
// Usage: standard_types LIBRARY VISUALIZER
//
// LIBRARY is the standard library implementation (libstdc++, libc++ or msstl), and VISUALIZER the
// kind of visualizers under test (gdb, lldb or natvis): the library's gdb pretty printers (for
// libc++, those in LLVM's source tree), lldb's formatters for the library, or STL.natvis. Only the
// objects whose types those visualizers support are visualized; for the pairings without any
// (libstdc++ and libc++ with natvis, MSVC's STL with gdb), none are. Other arguments make the
// program exit with 1.
#include "cxx_debug_visualize.hpp"

#include <any>
#include <array>
#include <atomic>
#include <bitset>
#include <chrono>
#include <complex>
#include <deque>
#include <filesystem>
#include <forward_list>
#include <functional>
#include <future>
#include <initializer_list>
#include <iterator>
#include <list>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <queue>
#include <regex>
#include <set>
#include <sstream>
#include <stack>
#include <string>
#include <string_view>
#include <system_error>
#include <thread>
#include <tuple>
#include <type_traits>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <valarray>
#include <variant>
#include <vector>

enum class stdlib
{
  unspecified,
  libstdcxx,
  libcxx,
  msstl,
};

enum class visualizer
{
  unspecified,
  gdb,
  lldb,
  natvis,
};

// The pairings of a standard library and a kind of visualizers that has visualizers, as flags.
enum pairings : unsigned
{
  libstdcxx_gdb = 1 << 0,
  libstdcxx_lldb = 1 << 1,
  libcxx_gdb = 1 << 2,
  libcxx_lldb = 1 << 3,
  msstl_lldb = 1 << 4,
  msstl_natvis = 1 << 5,
  all_pairings = (1 << 6) - 1,
};

int main(int argc, char** argv)
{
  stdlib lib = stdlib::unspecified;
  visualizer vis = visualizer::unspecified;
  {
    if (argc == 3)
    {
      std::string_view const lib_option = argv[1];

      if (lib_option == "libstdc++")
      {
        lib = stdlib::libstdcxx;
      }
      else if (lib_option == "libc++")
      {
        lib = stdlib::libcxx;
      }
      else if (lib_option == "msstl")
      {
        lib = stdlib::msstl;
      }

      std::string_view const vis_option = argv[2];

      if (vis_option == "gdb")
      {
        vis = visualizer::gdb;
      }
      else if (vis_option == "lldb")
      {
        vis = visualizer::lldb;
      }
      else if (vis_option == "natvis")
      {
        vis = visualizer::natvis;
      }
    }

    if (lib == stdlib::unspecified || vis == visualizer::unspecified)
    {
      return 1;
    }
  }

  unsigned current_pairing = 0;

  if (lib == stdlib::libstdcxx && vis == visualizer::gdb)
  {
    current_pairing = libstdcxx_gdb;
  }
  else if (lib == stdlib::libstdcxx && vis == visualizer::lldb)
  {
    current_pairing = libstdcxx_lldb;
  }
  else if (lib == stdlib::libcxx && vis == visualizer::gdb)
  {
    current_pairing = libcxx_gdb;
  }
  else if (lib == stdlib::libcxx && vis == visualizer::lldb)
  {
    current_pairing = libcxx_lldb;
  }
  else if (lib == stdlib::msstl && vis == visualizer::lldb)
  {
    current_pairing = msstl_lldb;
  }
  else if (lib == stdlib::msstl && vis == visualizer::natvis)
  {
    current_pairing = msstl_natvis;
  }

  auto const is_supported = [&](unsigned const pairings)
  {
    return (pairings & current_pairing) != 0;
  };

  // -- <any> --------------------------------------------------------------------------------------

  {
    std::any any = 42;
    if (is_supported(libstdcxx_gdb))
    {
      visualize(any);
    }

    std::any empty_any;
    if (is_supported(libstdcxx_gdb))
    {
      visualize(empty_any);
    }
  }

  // -- <array> ------------------------------------------------------------------------------------

  {
    std::array<int, 3> array{1, 2, 3};
    if (is_supported(msstl_natvis))
    {
      visualize(array);
    }
  }

  // -- <atomic> -----------------------------------------------------------------------------------

  {
    std::atomic<int> atomic{42};
    if (is_supported(libstdcxx_gdb | libcxx_lldb | msstl_lldb | msstl_natvis))
    {
      visualize(atomic);
    }

    std::atomic_flag atomic_flag = ATOMIC_FLAG_INIT;
    if (is_supported(msstl_natvis))
    {
      visualize(atomic_flag);
    }
  }

  // -- <bitset> -----------------------------------------------------------------------------------

  {
    std::bitset<8> bitset(0b1010'0101);
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_gdb | libcxx_lldb | msstl_natvis))
    {
      visualize(bitset);
    }
  }

  // -- <chrono> -----------------------------------------------------------------------------------

  {
    std::chrono::seconds duration{90};
    if (is_supported(libstdcxx_gdb | libcxx_lldb | msstl_natvis))
    {
      visualize(duration);
    }

    std::chrono::system_clock::time_point time_point{std::chrono::seconds{1'000'000'000}};
    if (is_supported(libstdcxx_gdb))
    {
      visualize(time_point);
    }
  }

  // -- <complex> ----------------------------------------------------------------------------------

  {
    std::complex<double> complex(1.5, -2.0);
    if (is_supported(msstl_natvis))
    {
      visualize(complex);
    }
  }

  // -- <deque> ------------------------------------------------------------------------------------

  {
    std::deque<int> deque{1, 2, 3};
    if (is_supported(all_pairings))
    {
      visualize(deque);
    }

    std::deque<int>::iterator deque_iterator = deque.begin() + 1;
    if (is_supported(libstdcxx_gdb))
    {
      visualize(deque_iterator);
    }

    std::deque<int>::iterator deque_end = deque.end();
    if (is_supported(libstdcxx_gdb))
    {
      visualize(deque_end);
    }
  }

  // -- <filesystem> -------------------------------------------------------------------------------

  {
    std::filesystem::path path = "/usr/include/stdio.h";
    if (is_supported(libstdcxx_gdb | msstl_natvis))
    {
      visualize(path);
    }
  }

  // -- <forward_list> -----------------------------------------------------------------------------

  {
    std::forward_list<int> forward_list{1, 2, 3};
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_lldb | msstl_lldb | msstl_natvis))
    {
      visualize(forward_list);
    }

    std::forward_list<int>::iterator forward_list_iterator = std::next(forward_list.begin());
    if (is_supported(libstdcxx_gdb | msstl_natvis))
    {
      visualize(forward_list_iterator);
    }

    std::forward_list<int>::iterator forward_list_end = forward_list.end();
    if (is_supported(libstdcxx_gdb | msstl_natvis))
    {
      visualize(forward_list_end);
    }
  }

  // -- <functional> -------------------------------------------------------------------------------

  {
    std::plus<int> plus;
    if (is_supported(msstl_natvis))
    {
      visualize(plus);
    }

    std::minus<int> minus;
    if (is_supported(msstl_natvis))
    {
      visualize(minus);
    }

    std::multiplies<int> multiplies;
    if (is_supported(msstl_natvis))
    {
      visualize(multiplies);
    }

    std::divides<int> divides;
    if (is_supported(msstl_natvis))
    {
      visualize(divides);
    }

    std::modulus<int> modulus;
    if (is_supported(msstl_natvis))
    {
      visualize(modulus);
    }

    std::negate<int> negate;
    if (is_supported(msstl_natvis))
    {
      visualize(negate);
    }
  }

  {
    std::equal_to<int> equal_to;
    if (is_supported(msstl_natvis))
    {
      visualize(equal_to);
    }

    std::not_equal_to<int> not_equal_to;
    if (is_supported(msstl_natvis))
    {
      visualize(not_equal_to);
    }

    std::greater<int> greater;
    if (is_supported(msstl_natvis))
    {
      visualize(greater);
    }

    std::less<int> less;
    if (is_supported(msstl_natvis))
    {
      visualize(less);
    }

    std::greater_equal<int> greater_equal;
    if (is_supported(msstl_natvis))
    {
      visualize(greater_equal);
    }

    std::less_equal<int> less_equal;
    if (is_supported(msstl_natvis))
    {
      visualize(less_equal);
    }
  }

  {
    std::logical_and<bool> logical_and;
    if (is_supported(msstl_natvis))
    {
      visualize(logical_and);
    }

    std::logical_or<bool> logical_or;
    if (is_supported(msstl_natvis))
    {
      visualize(logical_or);
    }

    std::logical_not<bool> logical_not;
    if (is_supported(msstl_natvis))
    {
      visualize(logical_not);
    }
  }

  {
    std::bit_and<int> bit_and;
    if (is_supported(msstl_natvis))
    {
      visualize(bit_and);
    }

    std::bit_or<int> bit_or;
    if (is_supported(msstl_natvis))
    {
      visualize(bit_or);
    }

    std::bit_xor<int> bit_xor;
    if (is_supported(msstl_natvis))
    {
      visualize(bit_xor);
    }

    std::bit_not<int> bit_not;
    if (is_supported(msstl_natvis))
    {
      visualize(bit_not);
    }
  }

  {
    std::hash<int> hash;
    if (is_supported(msstl_natvis))
    {
      visualize(hash);
    }
  }

  {
    int referenced = 42;
    std::reference_wrapper<int> reference_wrapper = std::ref(referenced);
    if (is_supported(msstl_natvis))
    {
      visualize(reference_wrapper);
    }
  }

  {
    std::function<int(int)> function = [](int value) { return value * 2; };
    if (is_supported(libcxx_lldb))
    {
      visualize(function);
    }
  }

  {
    std::string pattern = "needle";

    std::default_searcher default_searcher(pattern.begin(), pattern.end());
    if (is_supported(msstl_natvis))
    {
      visualize(default_searcher);
    }
  }

  // -- <future> -----------------------------------------------------------------------------------

  {
    std::promise<int> promise;
    if (is_supported(msstl_natvis))
    {
      visualize(promise);
    }

    promise.set_value(42);
    std::future<int> future = promise.get_future();
    if (is_supported(msstl_natvis))
    {
      visualize(future);
    }

    // sharing the future leaves it without a state, so this comes after it
    std::shared_future<int> shared_future = future.share();
    if (is_supported(msstl_natvis))
    {
      visualize(shared_future);
    }
  }

  {
    std::packaged_task<int()> packaged_task([] { return 42; });
    if (is_supported(msstl_natvis))
    {
      visualize(packaged_task);
    }
  }

  // -- <initializer_list> -------------------------------------------------------------------------

  {
    std::initializer_list<int> initializer_list = {1, 2, 3};
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | msstl_lldb | msstl_natvis))
    {
      visualize(initializer_list);
    }
  }

  // -- <iterator> ---------------------------------------------------------------------------------

  {
    std::vector<int> vector{1, 2, 3};

    std::reverse_iterator<std::vector<int>::iterator> reverse_iterator = vector.rbegin();
    if (is_supported(msstl_natvis))
    {
      visualize(reverse_iterator);
    }

    std::back_insert_iterator<std::vector<int>> back_insert_iterator(vector);
    if (is_supported(msstl_natvis))
    {
      visualize(back_insert_iterator);
    }

    std::insert_iterator<std::vector<int>> insert_iterator(vector, vector.begin() + 1);
    if (is_supported(msstl_natvis))
    {
      visualize(insert_iterator);
    }
  }

  {
    std::list<int> list{1, 2, 3};

    std::front_insert_iterator<std::list<int>> front_insert_iterator(list);
    if (is_supported(msstl_natvis))
    {
      visualize(front_insert_iterator);
    }
  }

  // -- <list> -------------------------------------------------------------------------------------

  {
    std::list<int> list{1, 2, 3};
    if (is_supported(all_pairings))
    {
      visualize(list);
    }

    std::list<int>::iterator list_iterator = std::next(list.begin());
    if (is_supported(libstdcxx_gdb | msstl_natvis))
    {
      visualize(list_iterator);
    }

    std::list<int>::iterator list_end = list.end();
    if (is_supported(libstdcxx_gdb))
    {
      visualize(list_end);
    }
  }

  // -- <map> --------------------------------------------------------------------------------------

  {
    std::map<int, std::string> map{{1, "one"}, {2, "two"}, {3, "three"}};
    if (is_supported(all_pairings))
    {
      visualize(map);
    }

    std::map<int, std::string>::iterator map_iterator = std::next(map.begin());
    if (is_supported(all_pairings))
    {
      visualize(map_iterator);
    }

    std::map<int, std::string>::iterator map_end = map.end();
    if (is_supported(libstdcxx_lldb | libcxx_gdb | libcxx_lldb | msstl_lldb | msstl_natvis))
    {
      visualize(map_end);
    }
  }

  {
    std::multimap<int, std::string> multimap{{1, "one"}, {1, "uno"}};
    if (is_supported(all_pairings))
    {
      visualize(multimap);
    }
  }

  // -- <memory> -----------------------------------------------------------------------------------

  {
    std::unique_ptr<int> unique_ptr = std::make_unique<int>(42);
    if (is_supported(all_pairings))
    {
      visualize(unique_ptr);
    }

    std::unique_ptr<int[]> unique_array = std::make_unique<int[]>(3);
    if (is_supported(all_pairings))
    {
      visualize(unique_array);
    }
  }

  {
    std::shared_ptr<int> shared_ptr = std::make_shared<int>(42);
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_gdb | libcxx_lldb | msstl_lldb))
    {
      visualize(shared_ptr);
    }

    std::weak_ptr<int> weak_ptr = shared_ptr;
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_gdb | libcxx_lldb | msstl_lldb))
    {
      visualize(weak_ptr);
    }
  }

  {
    std::allocator<int> allocator;
    if (is_supported(msstl_natvis))
    {
      visualize(allocator);
    }

    std::default_delete<int> default_delete;
    if (is_supported(msstl_natvis))
    {
      visualize(default_delete);
    }
  }

  // -- <mutex> ------------------------------------------------------------------------------------

  {
    std::mutex mutex;
    if (is_supported(msstl_natvis))
    {
      visualize(mutex);
    }

    std::recursive_mutex recursive_mutex;
    if (is_supported(msstl_natvis))
    {
      visualize(recursive_mutex);
    }

    std::timed_mutex timed_mutex;
    if (is_supported(msstl_natvis))
    {
      visualize(timed_mutex);
    }

    std::recursive_timed_mutex recursive_timed_mutex;
    if (is_supported(msstl_natvis))
    {
      visualize(recursive_timed_mutex);
    }

    std::once_flag once_flag;
    if (is_supported(msstl_natvis))
    {
      visualize(once_flag);
    }
  }

  {
    std::mutex mutex;

    std::lock_guard<std::mutex> lock_guard(mutex);
    if (is_supported(msstl_natvis))
    {
      visualize(lock_guard);
    }
  }

  {
    std::mutex mutex;

    std::unique_lock<std::mutex> unique_lock(mutex);
    if (is_supported(msstl_natvis))
    {
      visualize(unique_lock);
    }
  }

  {
    std::mutex first;
    std::mutex second;

    std::scoped_lock<std::mutex, std::mutex> scoped_lock(first, second);
    if (is_supported(msstl_natvis))
    {
      visualize(scoped_lock);
    }
  }

  {
    std::adopt_lock_t adopt_lock = std::adopt_lock;
    if (is_supported(msstl_natvis))
    {
      visualize(adopt_lock);
    }

    std::defer_lock_t defer_lock = std::defer_lock;
    if (is_supported(msstl_natvis))
    {
      visualize(defer_lock);
    }

    std::try_to_lock_t try_to_lock = std::try_to_lock;
    if (is_supported(msstl_natvis))
    {
      visualize(try_to_lock);
    }
  }

  // -- <optional> ---------------------------------------------------------------------------------

  {
    std::optional<int> optional = 42;
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_lldb | msstl_lldb | msstl_natvis))
    {
      visualize(optional);
    }

    std::optional<int> empty_optional;
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_lldb | msstl_lldb | msstl_natvis))
    {
      visualize(empty_optional);
    }

    std::nullopt_t nullopt = std::nullopt;
    if (is_supported(msstl_natvis))
    {
      visualize(nullopt);
    }
  }

  // -- <queue> ------------------------------------------------------------------------------------

  {
    std::queue<int> queue(std::deque<int>{1, 2});
    if (is_supported(libstdcxx_gdb | libcxx_gdb | libcxx_lldb | msstl_natvis))
    {
      visualize(queue);
    }
  }

  {
    std::priority_queue<int> priority_queue(std::less<int>(), std::vector<int>{1, 3, 2});
    if (is_supported(libstdcxx_gdb | libcxx_gdb | msstl_natvis))
    {
      visualize(priority_queue);
    }
  }

  // -- <regex> ------------------------------------------------------------------------------------

  {
    std::string text = "abc123 def456";

    std::regex regex("([a-z]+)([0-9]+)");
    if (is_supported(msstl_natvis))
    {
      visualize(regex);
    }

    std::smatch match_results = *std::sregex_iterator(text.begin(), text.end(), regex);
    if (is_supported(msstl_natvis))
    {
      visualize(match_results);
    }

    std::ssub_match sub_match = match_results[1];
    if (is_supported(msstl_natvis))
    {
      visualize(sub_match);
    }

    std::sregex_iterator regex_iterator(text.begin(), text.end(), regex);
    if (is_supported(msstl_natvis))
    {
      visualize(regex_iterator);
    }

    std::sregex_iterator regex_end;
    if (is_supported(msstl_natvis))
    {
      visualize(regex_end);
    }

    std::sregex_token_iterator regex_token_iterator(text.begin(), text.end(), regex, 1);
    if (is_supported(msstl_natvis))
    {
      visualize(regex_token_iterator);
    }

    std::sregex_token_iterator regex_token_end;
    if (is_supported(msstl_natvis))
    {
      visualize(regex_token_end);
    }
  }

  // -- <set> --------------------------------------------------------------------------------------

  {
    std::set<int> set{1, 2, 3};
    if (is_supported(all_pairings))
    {
      visualize(set);
    }

    std::set<int>::iterator set_iterator = std::next(set.begin());
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_gdb | msstl_lldb | msstl_natvis))
    {
      visualize(set_iterator);
    }

    std::set<int>::iterator set_end = set.end();
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_gdb | msstl_lldb | msstl_natvis))
    {
      visualize(set_end);
    }
  }

  {
    std::multiset<int> multiset{1, 2, 2};
    if (is_supported(all_pairings))
    {
      visualize(multiset);
    }
  }

  // -- <sstream> ----------------------------------------------------------------------------------

  {
    std::istringstream istringstream("1 2 3");
    if (is_supported(msstl_natvis))
    {
      visualize(istringstream);
    }

    std::ostringstream ostringstream("hello", std::ios_base::ate);
    if (is_supported(msstl_natvis))
    {
      visualize(ostringstream);
    }

    std::stringstream stringstream("hello");
    if (is_supported(msstl_natvis))
    {
      visualize(stringstream);
    }

    std::stringbuf stringbuf("hello");
    if (is_supported(msstl_natvis))
    {
      visualize(stringbuf);
    }
  }

  // -- <stack> ------------------------------------------------------------------------------------

  {
    std::stack<int> stack(std::deque<int>{1, 2});
    if (is_supported(libstdcxx_gdb | libcxx_gdb | msstl_natvis))
    {
      visualize(stack);
    }
  }

  // -- <string> -----------------------------------------------------------------------------------

  {
    std::string string = "hello";
    if (is_supported(all_pairings))
    {
      visualize(string);
    }

    std::string::iterator string_iterator = string.begin() + 1;
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_lldb | msstl_natvis))
    {
      visualize(string_iterator);
    }

    std::string::iterator string_end = string.end();
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_lldb | msstl_natvis))
    {
      visualize(string_end);
    }
  }

  {
    std::wstring wstring = L"hello";
    if (is_supported(all_pairings))
    {
      visualize(wstring);
    }
  }

  {
    std::u16string u16string = u"hello";
    if (is_supported(libstdcxx_gdb | libcxx_gdb | libcxx_lldb | msstl_lldb | msstl_natvis))
    {
      visualize(u16string);
    }
  }

  {
    std::u32string u32string = U"hello";
    if (is_supported(libstdcxx_gdb | libcxx_gdb | libcxx_lldb | msstl_lldb | msstl_natvis))
    {
      visualize(u32string);
    }
  }

  // -- <string_view> ------------------------------------------------------------------------------

  {
    std::string_view string_view = "hello";
    if (is_supported(all_pairings))
    {
      visualize(string_view);
    }
  }

  {
    std::wstring_view wstring_view = L"hello";
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_lldb | msstl_lldb | msstl_natvis))
    {
      visualize(wstring_view);
    }
  }

  {
    std::u16string_view u16string_view = u"hello";
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_lldb | msstl_lldb))
    {
      visualize(u16string_view);
    }
  }

  {
    std::u32string_view u32string_view = U"hello";
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_lldb | msstl_lldb))
    {
      visualize(u32string_view);
    }
  }

  // -- <system_error> -----------------------------------------------------------------------------

  {
    std::error_code error_code = std::make_error_code(std::errc::invalid_argument);
    if (is_supported(libstdcxx_gdb))
    {
      visualize(error_code);
    }

    std::error_condition error_condition = std::errc::invalid_argument;
    if (is_supported(libstdcxx_gdb))
    {
      visualize(error_condition);
    }
  }

  // -- <thread> -----------------------------------------------------------------------------------

  {
    std::thread thread;
    if (is_supported(msstl_natvis))
    {
      visualize(thread);
    }

    std::thread::id thread_id = std::this_thread::get_id();
    if (is_supported(msstl_natvis))
    {
      visualize(thread_id);
    }
  }

  // -- <tuple> ------------------------------------------------------------------------------------

  {
    std::tuple<int, double, std::string> tuple(1, 2.5, "three");
    if (is_supported(all_pairings))
    {
      visualize(tuple);
    }
  }

  // -- <type_traits> ------------------------------------------------------------------------------

  {
    std::integral_constant<int, 42> integral_constant;
    if (is_supported(libstdcxx_gdb))
    {
      visualize(integral_constant);
    }
  }

  // -- <unordered_map> ----------------------------------------------------------------------------

  {
    std::unordered_map<int, std::string> unordered_map{{1, "one"}, {2, "two"}};
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_gdb | libcxx_lldb | msstl_lldb))
    {
      visualize(unordered_map);
    }

    std::unordered_map<int, std::string>::iterator unordered_map_iterator = unordered_map.begin();
    if (is_supported(libcxx_gdb | libcxx_lldb | msstl_natvis))
    {
      visualize(unordered_map_iterator);
    }

    std::unordered_map<int, std::string>::iterator unordered_map_end = unordered_map.end();
    if (is_supported(libcxx_gdb | libcxx_lldb))
    {
      visualize(unordered_map_end);
    }
  }

  {
    std::unordered_multimap<int, std::string> unordered_multimap{{1, "one"}, {1, "uno"}};
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_gdb | libcxx_lldb | msstl_lldb))
    {
      visualize(unordered_multimap);
    }
  }

  // -- <unordered_set> ----------------------------------------------------------------------------

  {
    std::unordered_set<int> unordered_set{1, 2, 3};
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_gdb | libcxx_lldb | msstl_lldb))
    {
      visualize(unordered_set);
    }
  }

  {
    std::unordered_multiset<int> unordered_multiset{1, 2, 2};
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_gdb | libcxx_lldb | msstl_lldb))
    {
      visualize(unordered_multiset);
    }
  }

  // -- <utility> ----------------------------------------------------------------------------------

  {
    std::pair<int, std::string> pair(1, "one");
    if (is_supported(libstdcxx_gdb | libcxx_gdb | msstl_natvis))
    {
      visualize(pair);
    }
  }

  // -- <valarray> ---------------------------------------------------------------------------------

  {
    std::valarray<int> valarray{1, 2, 3, 4, 5, 6};
    if (is_supported(libcxx_lldb | msstl_natvis))
    {
      visualize(valarray);
    }

    std::slice_array<int> slice_array = valarray[std::slice(0, 3, 2)];
    if (is_supported(libcxx_lldb))
    {
      visualize(slice_array);
    }
  }

  // -- <variant> ----------------------------------------------------------------------------------

  {
    std::variant<int, std::string> variant = std::string("text");
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_lldb | msstl_lldb | msstl_natvis))
    {
      visualize(variant);
    }

    std::monostate monostate;
    if (is_supported(msstl_natvis))
    {
      visualize(monostate);
    }
  }

  // -- <vector> -----------------------------------------------------------------------------------

  {
    std::vector<int> vector{1, 2, 3};
    if (is_supported(all_pairings))
    {
      visualize(vector);
    }

    std::vector<int>::iterator vector_iterator = vector.begin() + 1;
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_lldb | msstl_natvis))
    {
      visualize(vector_iterator);
    }

    std::vector<int>::iterator vector_end = vector.end();
    if (is_supported(libstdcxx_gdb | libstdcxx_lldb | libcxx_lldb))
    {
      visualize(vector_end);
    }
  }

  {
    std::vector<bool> bool_vector{true, false, true};
    if (is_supported(all_pairings))
    {
      visualize(bool_vector);
    }

    std::vector<bool>::iterator bool_iterator = bool_vector.begin();
    if (is_supported(libstdcxx_gdb | msstl_natvis))
    {
      visualize(bool_iterator);
    }

    std::vector<bool>::iterator bool_end = bool_vector.end();
    if (is_supported(libstdcxx_gdb))
    {
      visualize(bool_end);
    }

    std::vector<bool>::reference bool_reference = bool_vector[0];
    if (is_supported(libstdcxx_gdb | msstl_natvis))
    {
      visualize(bool_reference);
    }
  }

  return 0;
}
