#include "engine.hpp"

#include <algorithm>
#include <cctype>
#include <charconv>
#include <cstdio>
#include <cstdlib>
#include <format>
#include <memory>
#include <ranges>
#include <stdexcept>
#include <string_view>

#include <dbghelp.h>
#include <oleauto.h>

// TODO:Debugging
#include <iostream>

using Microsoft::WRL::ComPtr;

namespace dbgeng_adapter {

namespace {

// Elements after this many are left out, in case a corrupt list never ends.
constexpr ULONG64 max_elements = 10000;

static std::wstring widen(std::string_view s)
{
  int const size = static_cast<int>(s.size());
  std::wstring w(MultiByteToWideChar(CP_UTF8, 0, s.data(), size, nullptr, 0), L'\0');
  MultiByteToWideChar(CP_UTF8, 0, s.data(), size, w.data(), static_cast<int>(w.size()));
  return w;
}

static std::string narrow(std::wstring_view const w)
{
  int const size = static_cast<int>(w.size());
  std::string s(WideCharToMultiByte(CP_UTF8, 0, w.data(), size, nullptr, 0, nullptr, nullptr),
                '\0');
  WideCharToMultiByte(CP_UTF8, 0, w.data(), size, s.data(), static_cast<int>(s.size()), nullptr,
                      nullptr);
  return s;
}

// Append to the file named by CXX_DEBUG_VISUALIZE_DBGENG_LOG, if set.
static void write_log(std::string_view const text)
{
  if (char const* const path = std::getenv("CXX_DEBUG_VISUALIZE_DBGENG_LOG"))
  {
    if (FILE* const log = std::fopen(path, "ab"))
    {
      std::fwrite(text.data(), 1, text.size(), log);
      std::fclose(log);
    }
  }
}

[[noreturn]] static void fail(std::string_view const what, HRESULT const hr)
{
  throw std::runtime_error(std::format("{} failed (HRESULT 0x{:08x})",
                                       what,
                                       static_cast<std::make_unsigned_t<HRESULT>>(hr)));
}

static void check(HRESULT const hr, std::string_view const what)
{
  if (FAILED(hr))
    fail(what, hr);
}


struct bstr_deleter
{
    void operator()(BSTR const bstr) const
    {
        SysFreeString(bstr);
    }
};

struct unique_bstr : std::unique_ptr<std::remove_pointer_t<BSTR>, bstr_deleter>
{
    using unique_ptr::unique_ptr;

    [[nodiscard]] std::wstring_view str() const
    {
        return *this ? std::wstring_view(get()) : std::wstring_view();
    }
};


class variant
{
  VARIANT m_data;

public:
  variant()
  {
    VariantInit(&m_data);
  }

  variant(variant const&) = delete;
  variant& operator=(variant const&) = delete;

  ~variant()
  {
    VariantClear(&m_data);
  }

  [[nodiscard]] VARIANT* get()
  {
    return &m_data;
  }

  [[nodiscard]] VARIANT* operator->()
  {
    return &m_data;
  }
};

std::filesystem::path default_dbgeng_dll_path()
{
  std::wstring_view const debuggers_path = L"Windows Kits\\10\\Debuggers";

#if defined(_M_ARM64)
  static constexpr std::wstring_view architecture = L"arm64";
#elif defined(_M_X64)
  static constexpr std::wstring_view architecture = L"x64";
#else
  static constexpr std::wstring_view architecture = L"x86";
#endif

  wchar_t program_files[MAX_PATH] = L"C:\\Program Files (x86)";
  GetEnvironmentVariableW(L"ProgramFiles(x86)", program_files, MAX_PATH);

  return std::filesystem::path(program_files) / debuggers_path / architecture / "dbgeng.dll";
}

// An argument quoted for the command line, as CommandLineToArgvW and the C runtime parse it.
static std::wstring quote(std::wstring const& arg)
{
  if (!arg.empty() && arg.find_first_of(L" \t\n\v\"") == std::wstring::npos)
    return arg;
  std::wstring quoted = L"\"";
  size_t backslashes = 0;
  for (wchar_t const c : arg)
  {
    if (c == L'\\')
    {
      ++backslashes;
      continue;
    }
    // Backslashes are literal, unless they precede a quote.
    quoted.append(c == L'"' ? backslashes * 2 + 1 : backslashes, L'\\');
    quoted += c;
    backslashes = 0;
  }
  quoted.append(backslashes * 2, L'\\');
  return quoted + L"\"";
}

static std::string type_name(IModelObject* const object)
{
  ComPtr<IDebugHostType> type;
  unique_bstr name;
  if (FAILED(object->GetTypeInfo(&type)) || !type || FAILED(type->GetName(std::out_ptr(name))))
    return "";
  return narrow(name.str());
}

static bool has_type_kind(IModelObject* const object, TypeKind const expected)
{
  ComPtr<IDebugHostType> type;
  TypeKind kind;
  return SUCCEEDED(object->GetTypeInfo(&type)) && type && SUCCEEDED(type->GetTypeKind(&kind)) &&
         kind == expected;
}

// The object that a reference refers to, else the object itself.
static ComPtr<IModelObject> referent(ComPtr<IModelObject> object)
{
  ModelObjectKind object_kind;
  ComPtr<IDebugHostType> type;
  TypeKind type_kind;
  PointerKind pointer_kind;
  bool const reference =
      (SUCCEEDED(object->GetKind(&object_kind)) && object_kind == ObjectTargetObjectReference) ||
      (SUCCEEDED(object->GetTypeInfo(&type)) && type && SUCCEEDED(type->GetTypeKind(&type_kind)) &&
       type_kind == TypePointer && SUCCEEDED(type->GetPointerKind(&pointer_kind)) &&
       (pointer_kind == PointerReference || pointer_kind == PointerRValueReference));
  ComPtr<IModelObject> target;
  if (reference && SUCCEEDED(object->Dereference(&target)))
    return target;
  return object;
}

template<typename T>
static std::string to_chars(T const& value)
{
    std::string string;

    while (true)
    {
        string.resize(std::max<size_t>(string.capacity(), 1));

        auto const [ptr, ec] = std::to_chars(
            string.data(),
            string.data() + string.size(),
            value);

        if (ec == std::errc())
        {
            string.resize(static_cast<size_t>(ptr - string.data()));
            return string;
        }

        string.push_back(0);
    }
}

// A number, as a debugger shows it: pointers in hexadecimal, and characters also as such.
static std::string format(VARIANT const& v, bool const pointer)
{
  auto const format_character = [&](int code)
  {
    std::string text = to_chars(code);

    if (code >= 0x20 && code < 0x7f)
      text = std::format("{} '{}'", text, static_cast<char>(code));

    return text;
  };

  if (pointer && v.vt == VT_UI4)
    return std::format("0x{:08x}", v.ulVal);

  if (pointer && v.vt == VT_UI8)
    return std::format("0x{:016x}", v.ullVal);

  switch (v.vt)
  {
  case VT_BOOL:
    return v.boolVal ? "true" : "false";
  case VT_I1:
    return format_character(v.cVal);
  case VT_UI1:
    return format_character(v.bVal);
  case VT_I2:
    return to_chars(v.iVal);
  case VT_UI2:
    return to_chars(v.uiVal);
  case VT_I4:
    return to_chars(v.lVal);
  case VT_UI4:
    return to_chars(v.ulVal);
  case VT_I8:
    return to_chars(v.llVal);
  case VT_UI8:
    return to_chars(v.ullVal);
  case VT_INT:
    return to_chars(v.intVal);
  case VT_UINT:
    return to_chars(v.uintVal);
  case VT_R4:
    return to_chars(v.fltVal);
  case VT_R8:
    return to_chars(v.dblVal);
  case VT_BSTR:
    return narrow(v.bstrVal);
  default:
    return "";
  }
}

// Whether a key is shown: methods are not, nor keys without a value.
static bool shown(IModelObject* const object, IKeyStore* const metadata)
{
  ModelObjectKind kind;
  if (FAILED(object->GetKind(&kind)) || kind == ObjectMethod || kind == ObjectNoValue)
    return false;

  if (metadata != nullptr) {
    ComPtr<IModelObject> prefer_show;
    if (SUCCEEDED(metadata->GetKeyValue(L"PreferShow", &prefer_show, nullptr))) {
      variant prefer_show_value;
      if (SUCCEEDED(prefer_show->GetIntrinsicValue(prefer_show_value.get()))) {
        if (prefer_show_value->vt == VT_BOOL)
          return prefer_show_value->boolVal;
      }
    }
  }

  return true;
}

} // namespace


STDMETHODIMP output_collector::QueryInterface(REFIID id, void** const object)
{
  if (id == __uuidof(IUnknown) || id == __uuidof(IDebugOutputCallbacksWide))
  {
    *object = static_cast<IDebugOutputCallbacksWide*>(this);
    return S_OK;
  }
  else
  {
    *object = nullptr;
    return E_NOINTERFACE;
  }
}

STDMETHODIMP_(ULONG) output_collector::AddRef()
{
  return 1;
}

STDMETHODIMP_(ULONG) output_collector::Release()
{
  return 1;
}

STDMETHODIMP output_collector::Output(ULONG, PCWSTR const output)
{
  m_output += output;
  write_log(narrow(output));
  return S_OK;
}


std::string debugger::execute(std::wstring const& command)
{
  m_control->ExecuteWide(DEBUG_OUTCTL_THIS_CLIENT, command.c_str(), DEBUG_EXECUTE_NOT_LOGGED);
  return narrow(m_output.flush());
}

std::string debugger::display(IModelObject* const object)
{
  // Natvis DisplayStrings, and errors, are displayed this way.
  ComPtr<IStringDisplayableConcept> displayable;

  unique_bstr text;
  if (SUCCEEDED(object->GetConcept(__uuidof(IStringDisplayableConcept), &displayable, nullptr)) &&
      SUCCEEDED(displayable->ToDisplayString(object, m_decimal.Get(), std::out_ptr(text))))
    return narrow(text.str());

  ModelObjectKind kind;
  if (FAILED(object->GetKind(&kind)))
    return "";

  variant intrinsic;
  if (kind == ObjectIntrinsic && SUCCEEDED(object->GetIntrinsicValue(intrinsic.get())))
  {
    bool const pointer = has_type_kind(object, TypePointer);
    std::string formatted = format(*intrinsic.get(), pointer);

    // As other debuggers show it, a pointer to an object is followed by the object's display
    // string, if it has one.
    bool const null = intrinsic->vt == VT_UI8 ? intrinsic->ullVal == 0 : intrinsic->ulVal == 0;
    ComPtr<IModelObject> target;
    if (pointer && !null && SUCCEEDED(object->Dereference(&target)) &&
        has_type_kind(target.Get(), TypeUDT))
    {
      std::string const target_text = display(target.Get());
      if (!target_text.empty() && target_text != "{...}")
        formatted += std::format(" {}", target_text);
    }
    return formatted;
  }

  if (kind == ObjectTargetObject)
    return "{...}";

  return "";
}

value debugger::make_value(std::string name, IModelObject* object)
{
  return {std::move(name), display(referent(object).Get()), type_name(object)};
}

// The children of an object, as the data model shows them: the keys (natvis Items) and elements
// (other natvis items) of a visualized object, else its fields.
std::vector<value> debugger::children(IModelObject* object)
{
  std::vector<value> result;

  // Whether a visualizer expands the object (a natvis <Expand>), even if into nothing, which
  // leaves the fields out, as dx shows them only under [<Raw View>].
  bool expanded = false;

  ComPtr<IKeyEnumerator> keys;
  if (SUCCEEDED(object->EnumerateKeyValues(&keys)))
  {
    while (true)
    {
      unique_bstr name;
      ComPtr<IModelObject> child;
      ComPtr<IKeyStore> metadata;

      HRESULT const hr = keys->GetNext(std::out_ptr(name), &child, &metadata);
      if (hr == E_BOUNDS || (FAILED(hr) && !child))
        break;

      // A conditional natvis Item has no value when its condition is false.
      ModelObjectKind kind;
      if (SUCCEEDED(child->GetKind(&kind)) && kind == ObjectNoValue)
        expanded = true;

      if (shown(child.Get(), metadata.Get()))
        result.push_back(make_value(narrow(name.str()), child.Get()));
    }
  }

  ComPtr<IIterableConcept> iterable;
  ComPtr<IModelIterator> iterator;
  ULONG64 dimensions = 0;
  if (SUCCEEDED(object->GetConcept(__uuidof(IIterableConcept), &iterable, nullptr)) &&
      SUCCEEDED(iterable->GetIterator(object, &iterator)))
  {
    expanded = true;
    if (FAILED(iterable->GetDefaultIndexDimensionality(object, &dimensions)))
      dimensions = 0;

    for (ULONG64 i = 0; i < max_elements; ++i)
    {
      ComPtr<IModelObject> element;
      std::vector<IModelObject*> indexers(dimensions, nullptr);
      HRESULT const hr = iterator->GetNext(&element, dimensions, indexers.data(), nullptr);
      if (hr == E_BOUNDS || (FAILED(hr) && !element))
        break;

      // e.g. [0], or [1,2] for a two-dimensional array. The index may also be the Name of a
      // natvis Item, such as [9], which is used as it is.
      std::string name = indexers.empty() ? std::to_string(i) : "";
      for (IModelObject* const indexer : indexers)
      {
        if (!name.empty())
          name += ',';

        if (indexer)
        {
          name += display(indexer);
          indexer->Release();
        }
      }

      if (!name.starts_with('['))
        name = std::format("[{}]", name);

      result.push_back(make_value(name, element.Get()));
    }
  }

  if (!expanded && result.empty())
  {
    ComPtr<IRawEnumerator> fields;
    if (SUCCEEDED(object->EnumerateRawValues(SymbolField, RawSearchNone, &fields)))
    {
      while (true)
      {
        unique_bstr name;
        SymbolKind kind;
        ComPtr<IModelObject> field;

        HRESULT const hr = fields->GetNext(std::out_ptr(name), &kind, &field);
        if (hr == E_BOUNDS || (FAILED(hr) && !field))
          break;

        result.push_back(make_value(narrow(name.str()), field.Get()));
      }
    }
  }

  return result;
}

debugger::debugger(std::string const& path)
{
  auto const dll = path.empty() ? default_dbgeng_dll_path() : std::filesystem::path(path);

  // With dbgeng.dll's own directory searched first for the DLLs it loads (dbghelp.dll,
  // dbgmodel.dll), rather than the older versions in System32.
  HMODULE const dbgeng = LoadLibraryExW(dll.c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
  if (dbgeng == NULL)
    throw std::runtime_error(std::format("cannot load {}; install the Debugging Tools for Windows",
                                         dll.string()));

  auto const create = reinterpret_cast<decltype(&DebugCreate)>(
      reinterpret_cast<void*>(GetProcAddress(dbgeng, "DebugCreate")));

  if (!create)
    fail(std::format("finding DebugCreate in {}", dll.string()), HRESULT_FROM_WIN32(GetLastError()));

  check(create(__uuidof(IDebugClient5), &m_client), "DebugCreate");
  check(m_client.As(&m_control), "IDebugControl4");
  check(m_client.As(&m_symbols), "IDebugSymbols3");
  check(m_client->SetOutputCallbacksWide(&m_output), "SetOutputCallbacks");

  ComPtr<IHostDataModelAccess> access;
  check(m_client.As(&access), "IHostDataModelAccess");
  check(access->GetDataModel(&m_manager, &m_host), "GetDataModel");

  check(m_manager->CreateMetadataStore(nullptr, &m_decimal), "CreateMetadataStore");
  ComPtr<IModelObject> radix;
  VARIANT ten;
  ten.vt = VT_UI4;
  ten.ulVal = 10;
  check(m_manager->CreateIntrinsicObject(ObjectIntrinsic, &ten, &radix), "CreateIntrinsicObject");
  check(m_decimal->SetKey(L"PreferredRadix", radix.Get(), nullptr), "SetKey");
  // Also for what the engine formats itself, as `n 10` does.
  check(m_control->SetRadix(10), "SetRadix");

  // Stop at the initial breakpoint, which the loader hits before the program's own code runs, and
  // when the program exits.
  for (ULONG const filter : {DEBUG_FILTER_INITIAL_BREAKPOINT, DEBUG_FILTER_EXIT_PROCESS})
  {
    DEBUG_SPECIFIC_FILTER_PARAMETERS parameters;
    check(m_control->GetSpecificFilterParameters(filter, 1, &parameters), "GetFilterParameters");
    parameters.ExecutionOption = DEBUG_FILTER_BREAK;
    check(m_control->SetSpecificFilterParameters(filter, 1, &parameters), "SetFilterParameters");
  }
}

debugger::~debugger()
{
  m_client->TerminateProcesses();
  m_client->EndSession(DEBUG_END_ACTIVE_TERMINATE);
  m_client->SetOutputCallbacksWide(nullptr);
}

void debugger::launch(std::filesystem::path const& program, std::vector<std::string> const& args,
                      std::filesystem::path const& cwd)
{
  // Symbols only from next to the program, not from Microsoft's symbol server (for system DLLs), so
  // that nothing is downloaded; with source line information.
  auto const program_directory = program.parent_path();

  check(m_symbols->SetSymbolPathWide(program_directory.c_str()), "SetSymbolPath");
  check(m_symbols->AddSymbolOptions(SYMOPT_LOAD_LINES), "AddSymbolOptions");

  std::wstring command_line = quote(program.native());
  for (std::string const& arg : args)
  {
      command_line += L' ';
      command_line += quote(widen(arg));
  }

  DEBUG_CREATE_PROCESS_OPTIONS options = {};
  options.CreateFlags = DEBUG_ONLY_THIS_PROCESS;
  check(m_client->CreateProcess2Wide(0, command_line.data(), &options, sizeof options,
                                     cwd.empty() ? nullptr : cwd.c_str(), nullptr),
        "CreateProcess");
  check(m_control->WaitForEvent(DEBUG_WAIT_DEFAULT, INFINITE), "WaitForEvent");

  // Load the program's symbols now: the engine defers loading them until they are needed, and
  // finding the code for a line does not count.
  check(m_symbols->ReloadWide(std::format(L"/f {}", program.filename().native()).c_str()),
        "loading symbols");

  m_output.flush();
}

std::string debugger::load_natvis(std::string_view const path)
{
  std::wstring const wide_path = widen(path);

  std::wstring const command = std::format(L".nvload \"{}\"", wide_path);
  m_control->ExecuteWide(DEBUG_OUTCTL_THIS_CLIENT, command.c_str(), DEBUG_EXECUTE_NOT_LOGGED);

  std::wstring output = m_output.flush();
  if (output == std::format(L"Successfully loaded visualizers in \"{}\"\n", wide_path))
    output.clear();

  return narrow(output);
}

uint32_t debugger::set_breakpoint(std::string const& file, uint32_t line)
{
  ULONG64 offset = 0;
  HRESULT const hr = m_symbols->GetOffsetByLineWide(line, widen(file).c_str(), &offset);
  if (FAILED(hr))
    fail(std::format("finding code for {}:{}", file, line), hr);

  // The engine owns its breakpoints; they are not reference counted.
  IDebugBreakpoint2* breakpoint = nullptr;
  check(m_control->AddBreakpoint2(DEBUG_BREAKPOINT_CODE, DEBUG_ANY_ID, &breakpoint),
        "AddBreakpoint");
  check(breakpoint->SetOffset(offset), "SetOffset");
  check(breakpoint->AddFlags(DEBUG_BREAKPOINT_ENABLED), "AddFlags");

  // The code may belong to a later line.
  ULONG actual_line = line;
  m_symbols->GetLineByOffsetWide(offset, &actual_line, nullptr, 0, nullptr, nullptr);
  return actual_line;
}

stop_info debugger::run()
{
  // Continuing after an exception does not handle it, which would run the faulting code again:
  // the program gets the exception, and one it does not handle ends it.
  ULONG status = std::exchange(m_exception, false) ? DEBUG_STATUS_GO_NOT_HANDLED
                                                   : DEBUG_STATUS_GO;

  while (true)
  {
    check(m_control->SetExecutionStatus(status), "SetExecutionStatus");
    HRESULT const hr = m_control->WaitForEvent(DEBUG_WAIT_DEFAULT, INFINITE);

    ULONG type = 0;
    ULONG process = 0;
    ULONG thread = 0;
    union
    {
      DEBUG_LAST_EVENT_INFO_EXIT_PROCESS exit;
      DEBUG_LAST_EVENT_INFO_EXCEPTION exception;
    } extra = {};
    char description[512] = "";

    // Without a program, as after it has exited, waiting fails.
    if (FAILED(hr) ||
        FAILED(m_control->GetLastEventInformation(&type,
                                                  &process,
                                                  &thread,
                                                  &extra,
                                                  sizeof(extra),
                                                  /*ExtraInformationUsed=*/nullptr,
                                                  description,
                                                  sizeof(description),
                                                  /*DescriptionUsed=*/nullptr)))
      return {stop_reason::exited};

    if (type == DEBUG_EVENT_EXIT_PROCESS)
      return {stop_reason::exited, "", extra.exit.ExitCode};

    if (type == DEBUG_EVENT_BREAKPOINT)
      return {stop_reason::breakpoint};

    // An exception the program may still handle (its first chance) is given to it. If it does not
    // handle it, the program stops again (its second chance), so that a crash stops it once.
    if (type == DEBUG_EVENT_EXCEPTION && extra.exception.FirstChance)
    {
      status = DEBUG_STATUS_GO_NOT_HANDLED;
      continue;
    }

    // E.g. "Access violation - code c0000005 (!!! second chance !!!)"
    m_exception = true;

    return {stop_reason::exception, description};
  }
}

frame debugger::top_frame()
{
  DEBUG_STACK_FRAME top = {};
  ULONG frames = 0;
  check(m_control->GetStackTrace(0, 0, 0, &top, 1, &frames), "GetStackTrace");
  if (frames == 0)
    throw std::runtime_error("the thread has no stack frames");

  frame result;
  wchar_t name[1024];
  ULONG64 displacement = 0;
  char text[32];
  if (SUCCEEDED(m_symbols->GetNameByOffsetWide(top.InstructionOffset, name, std::size(name),
                                               nullptr, &displacement)))
  {
    result.name = narrow(name);

    if (displacement)
      result.name += std::format("+0x{:x}", displacement);
  }
  else
  {
    result.name = std::format("{:x}", top.InstructionOffset);
  }

  wchar_t file[MAX_PATH * 2];
  ULONG line = 0;
  if (SUCCEEDED(m_symbols->GetLineByOffsetWide(top.InstructionOffset, &line, file, std::size(file),
                                               nullptr, nullptr)))
  {
    result.file = narrow(file);
    result.line = line;
  }
  return result;
}

value debugger::evaluate(std::string const& expression, std::vector<value>& children)
{
  ComPtr<IDebugHostContext> context;
  check(m_host->GetCurrentContext(&context), "GetCurrentContext");
  ComPtr<IDebugHostEvaluator> evaluator;
  check(m_host.As(&evaluator), "IDebugHostEvaluator");

  ComPtr<IModelObject> object;
  HRESULT const hr = evaluator->EvaluateExpression(context.Get(), widen(expression).c_str(),
                                                   nullptr, &object, nullptr);
  if (FAILED(hr))
  {
    std::string const message = object ? display(object.Get()) : "";

    if (message.empty())
        fail(std::format("evaluating {}", expression), hr);

    throw std::runtime_error(message);
  }

  ComPtr<IModelObject> const target = referent(object);
  children = this->children(target.Get());
  return make_value(expression, object.Get());
}

} // namespace dbgeng_adapter
