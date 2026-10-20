// The Windows debug engine (DbgEng), debugging one program. Values come from its data model, which
// applies natvis visualizers.
#pragma once

#include <filesystem>
#include <string>
#include <vector>

#include <windows.h>

#include <dbgeng.h>
#include <dbgmodel.h>
#include <wrl/client.h>

namespace dbgeng_adapter {

// A value as the data model shows it; `type` is empty if it has none.
struct value
{
  std::string name;
  std::string text;
  std::string type;
};

struct frame
{
  std::string name;
  std::string file;
  uint32_t line = 0;
};

enum class stop_reason
{
    breakpoint,
    exception,
    exited,
};

struct stop_info
{
  stop_reason reason;
  std::string description;
  uint32_t exit_code = 0;
};

// Collects what the engine prints, and appends it to the file named by
// CXX_DEBUG_VISUALIZE_DBGENG_LOG, if set.
class output_collector : public IDebugOutputCallbacksWide
{
  std::wstring m_output;

public:
  STDMETHOD(QueryInterface)(REFIID id, void** object) override;
  // It outlives the engine's use of it, so it is not reference counted.
  STDMETHOD_(ULONG, AddRef)() override;
  STDMETHOD_(ULONG, Release)() override;
  STDMETHOD(Output)(ULONG mask, PCWSTR output) override;

  std::wstring flush()
  {
      std::wstring output = std::move(m_output);
      m_output.clear();

      return output;
  }
};

// All strings are UTF-8. Failures are thrown as std::runtime_error.
class debugger
{
  // Registered with the client, so declared first, to be destroyed last.
  output_collector m_output;

  // dbgeng.dll stays loaded until this program exits.
  Microsoft::WRL::ComPtr<IDebugClient5> m_client;
  Microsoft::WRL::ComPtr<IDebugControl4> m_control;
  Microsoft::WRL::ComPtr<IDebugSymbols3> m_symbols;
  Microsoft::WRL::ComPtr<IDataModelManager> m_manager;
  Microsoft::WRL::ComPtr<IDebugHost> m_host;
  // Metadata for showing integers in decimal, as other debuggers do.
  Microsoft::WRL::ComPtr<IKeyStore> m_decimal;

  // Whether the program stopped at an exception, which it is given back when it runs again.
  bool m_exception = false;

  // Run a command, and return what it printed.
  std::string execute(std::wstring const& command);

  std::string display(IModelObject* object);
  value make_value(std::string name, IModelObject* object);
  std::vector<value> children(IModelObject* object);

public:
  // Load dbgeng.dll from `path`, a directory or a file in it, or from the Debugging Tools for
  // Windows if it is empty.
  explicit debugger(std::string const& path);
  debugger(debugger const&) = delete;
  debugger& operator=(debugger const&) = delete;
  ~debugger();

  // Start the program, stopped before it runs any of its own code.
  void launch(std::filesystem::path const& program, std::vector<std::string> const& args,
              std::filesystem::path const& cwd);

  // Unload all natvis files, including those that the engine loads by default.
  void unload_natvis();

  // Load a natvis file; return what the engine printed if that failed, else "".
  std::string load_natvis(std::string_view path);

  // Set a breakpoint on a line and return the line it was placed on.
  uint32_t set_breakpoint(std::string const& file, uint32_t line);

  // Run the program until it stops or exits.
  stop_info run();

  frame top_frame();

  // Evaluate an expression in the top frame, with its children.
  value evaluate(std::string const& expression, std::vector<value>& children);
};

} // namespace dbgeng_adapter
