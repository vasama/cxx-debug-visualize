// A debug adapter for the Windows debug engine (DbgEng), for cxx-debug-visualize --adapter dbgeng.
// Its launch arguments are program, args, cwd, visualizerFile, defaultVisualizers (false to unload
// the natvis files that the engine loads by default, such as the Debugging Tools'), and
// debuggerPath (the directory of dbgeng.dll, or a file in it such as cdb.exe).
//
// Only what cxx-debug-visualize uses is implemented: one program, reported as a single thread 1,
// line breakpoints, the top stack frame, and values with their children (one level deep). Requests
// are handled one at a time, and none are read while the program runs.
//
// Set CXX_DEBUG_VISUALIZE_DBGENG_LOG to a file name to record what the engine prints.

#include "engine.hpp"

#include <cstdio>
#include <exception>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <ranges>
#include <stdexcept>

#include <nlohmann/json.hpp>

#include <fcntl.h>
#include <io.h>

namespace {

using nlohmann::json;
using namespace dbgeng_adapter;

class adapter
{
  uint32_t m_seq = 0;
  uint32_t m_breakpoint_count = 0;

  std::optional<debugger> m_debugger;
  // the children of each evaluated value, by variablesReference - 1, until the program runs
  std::vector<std::vector<value>> m_children;

  using continuation_type = void (adapter::*)();
  continuation_type m_continuation = nullptr;

public:
  [[nodiscard]] static int run()
  {
    return adapter().run_impl();
  }

private:
  adapter() = default;
  adapter(adapter const&) = delete;
  adapter& operator=(adapter const&) = delete;

  debugger& debugger()
  {
    if (!m_debugger)
      throw std::runtime_error("not launched");

    return *m_debugger;
  }

  // -- Protocol --------------------------------------------------------------

  static std::optional<json> read_message()
  {
    std::optional<size_t> length;
    std::string line;
    while (std::getline(std::cin, line))
    {
      if (!line.empty() && line.back() == '\r')
        line.pop_back();
      if (line.empty())
        break;
      std::string const header = "Content-Length:";
      if (line.compare(0, header.size(), header) == 0)
        length = std::stoul(line.substr(header.size()));
    }
    if (!std::cin || !length)
      return std::nullopt;
    std::string body(*length, '\0');
    if (!std::cin.read(body.data(), body.size()))
      return std::nullopt;
    return json::parse(body);
  }

  void send(json message)
  {
    message["seq"] = ++m_seq;
    // Invalid UTF-8 (e.g. in an exception's description) is replaced, rather than failing.
    std::string const data = message.dump(-1, ' ', false, json::error_handler_t::replace);
    std::cout << "Content-Length: " << data.size() << "\r\n\r\n" << data << std::flush;
  }

  void event(std::string name, json body = json::object())
  {
    send({{"type", "event"}, {"event", std::move(name)}, {"body", std::move(body)}});
  }

  // -- Requests --------------------------------------------------------------

  void send_initialized()
  {
    event("initialized");
  }

  json on_initialize(json const&)
  {
    return {{"supportsConfigurationDoneRequest", true}};
  }

  json on_launch(json const& args)
  {
    m_debugger.emplace(args.value("debuggerPath", ""));
    m_debugger->launch(args.at("program").get<std::string>(),
                       args.value("args", std::vector<std::string>()),
                       args.value("cwd", ""));

    if (!args.value("defaultVisualizers", true))
      m_debugger->unload_natvis();

    std::string const natvis = args.value("visualizerFile", "");
    if (!natvis.empty())
    {
      std::string const error = m_debugger->load_natvis(natvis);
      if (!error.empty())
        event("output", {{"category", "console"}, {"output", std::format("[Natvis] {}\n", error)}});
    }

    m_continuation = &adapter::send_initialized;
    return json::object();
  }

  json on_setBreakpoints(json const& args)
  {
    std::string const path = args.at("source").at("path").get<std::string>();

    json breakpoints = json::array();
    for (json const& requested : args.value("breakpoints", json::array()))
    {
      json breakpoint{{"id", ++m_breakpoint_count}};

      try
      {
        breakpoint["line"] = debugger().set_breakpoint(path, requested.at("line").get<unsigned>());
        breakpoint["verified"] = true;
      }
      catch (std::exception const& e)
      {
        breakpoint["message"] = e.what();
        breakpoint["verified"] = false;
      }

      breakpoints.push_back(std::move(breakpoint));
    }

    return {{"breakpoints", std::move(breakpoints)}};
  }

  json on_configurationDone(json const&)
  {
    m_continuation = &adapter::run_debuggee;
    return json::object();
  }

  json on_threads(json const&)
  {
    return {{"threads", json::array({{{"id", 1}, {"name", "main"}}})}};
  }

  json on_stackTrace(json const&)
  {
    frame const top = debugger().top_frame();
    json frame{{"id", 1}, {"name", top.name}, {"line", top.line}, {"column", 0}};
    if (!top.file.empty())
    {
      std::string const name = top.file.substr(top.file.find_last_of("\\/") + 1);
      frame["source"] = {{"path", top.file}, {"name", name}};
    }
    return {{"stackFrames", json::array({std::move(frame)})}, {"totalFrames", 1}};
  }

  json on_evaluate(json const& args)
  {
    std::vector<value> children;
    value const value = debugger().evaluate(args.at("expression").get<std::string>(), children);
    size_t reference = 0;
    if (!children.empty())
    {
      m_children.push_back(std::move(children));
      reference = m_children.size();
    }
    json body{{"result", value.text}, {"variablesReference", reference}};
    if (!value.type.empty())
      body["type"] = value.type;
    return body;
  }

  json on_variables(json const& args)
  {
    auto const reference = args.at("variablesReference").get<size_t>();
    if (reference == 0 || reference > m_children.size())
      throw std::runtime_error("invalid variablesReference");

    json variables = json::array();
    for (value const& child : m_children[reference - 1])
    {
      json variable{{"name", child.name}, {"value", child.text}, {"variablesReference", 0}};
      if (!child.type.empty())
        variable["type"] = child.type;
      variables.push_back(std::move(variable));
    }
    return {{"variables", std::move(variables)}};
  }

  json on_continue(json const&)
  {
    m_continuation = &adapter::run_debuggee;
    return {{"allThreadsContinued", true}};
  }

  json on_disconnect(json const&)
  {
    return json::object();
  }

  // -- Running ---------------------------------------------------------------

  // Run the program until it stops or exits, and report which.
  void run_debuggee()
  {
    m_children.clear();

    stop_info const stop = debugger().run();

    switch (stop.reason)
    {
    case stop_reason::breakpoint:
      event("stopped", {{"reason", "breakpoint"}, {"threadId", 1}});
      break;

    case stop_reason::exception:
      event("stopped",
            {{"reason", "exception"},
             {"threadId", 1},
             {"text", stop.description},
             {"description", stop.description}});
      break;

    case stop_reason::exited:
      event("exited", {{"exitCode", stop.exit_code}});
      event("terminated");
      break;
    }
  }

  int run_impl()
  {
    using handler_type = json (adapter::*)(json const&);
    using handler_pair = std::pair<std::string_view, handler_type>;

    static constexpr handler_pair handlers[] = {
        {"configurationDone", &adapter::on_configurationDone},
        {"continue", &adapter::on_continue},
        {"disconnect", &adapter::on_disconnect},
        {"evaluate", &adapter::on_evaluate},
        {"initialize", &adapter::on_initialize},
        {"launch", &adapter::on_launch},
        {"setBreakpoints", &adapter::on_setBreakpoints},
        {"stackTrace", &adapter::on_stackTrace},
        {"threads", &adapter::on_threads},
        {"variables", &adapter::on_variables},
    };

    while (std::optional<json> const request = read_message())
    {
      std::string const command = request->value("command", "");

      json response{{"type", "response"},
                    {"request_seq", request->value<uint32_t>("seq", 0)},
                    {"command", command},
                    {"success", true}};

      try
      {
        auto const it = std::ranges::find(handlers, command, &handler_pair::first);
        if (it == std::end(handlers))
          throw std::runtime_error(std::format("unsupported request: {}", command));

        response["body"] = (this->*it->second)(request->value("arguments", json::object()));
      }
      catch (std::exception const& e)
      {
        response["success"] = false;
        response["message"] = e.what();
      }

      auto const continuation = std::exchange(m_continuation, nullptr);

      send(std::move(response));

      if (continuation)
      {
        try
        {
          (this->*continuation)();
        }
        catch (std::exception const& e)
        {
          std::cerr << e.what() << std::endl;
          event("output", {{"category", "important"}, {"output", std::format("{}\n", e.what())}});
          event("terminated");
        }
      }

      if (command == "disconnect")
        break;
    }

    // The program is terminated with the debugger.
    m_debugger.reset();

    return 0;
  }
};

} // namespace

int main()
{
  // Messages are measured in bytes, which translating line endings would change.
  _setmode(_fileno(stdin), _O_BINARY);
  _setmode(_fileno(stdout), _O_BINARY);

  return adapter::run();
}
