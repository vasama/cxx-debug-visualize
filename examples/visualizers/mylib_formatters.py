# lldb formatters for the toy types in include/mylib/containers.hpp; the
# counterpart of mylib.natvis and mylib_printers.py, written so
# that lldb shows the same trees as far as it can.
#
# Loaded with `command script import`, which calls __lldb_init_module.

import lldb


# A child named `name` that shows the value `value`.
def _renamed(name, value):
    return value.CreateValueFromAddress(name, value.GetLoadAddress(), value.GetType())


# The object itself, with its real members rather than the synthetic children,
# also for formatters that apply to pointers to it.
def _object(valobj):
    valobj = valobj.GetNonSyntheticValue()
    if valobj.GetType().IsPointerType():
        valobj = valobj.Dereference().GetNonSyntheticValue()
    return valobj


def _member(valobj, name):
    return _object(valobj).GetChildMemberWithName(name)


def point_summary(valobj, internal_dict):
    x = _member(valobj, "x").GetValueAsSigned()
    y = _member(valobj, "y").GetValueAsSigned()
    return f"({x}, {y})"


# the char *, as `0x... "text"`, like natvis's {m_data,s8}
def string_summary(valobj, internal_dict):
    data = _member(valobj, "m_data")
    return f"{data.GetValue()} {data.GetSummary()}"


class StringProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def num_children(self):
        return 1

    def get_child_at_index(self, index):
        return _renamed("[size]", _member(self.valobj, "m_length"))


# `{ size=N }`, N being the value of the member `member`
def size_summary(member):
    def summary(valobj, internal_dict):
        return f"{{ size={_member(valobj, member).GetValueAsUnsigned()} }}"

    return summary


vector_summary = size_summary("m_size")
list_summary = size_summary("m_count")
int_map_summary = size_summary("m_count")


class VectorProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def num_children(self):
        return 2 + _member(self.valobj, "m_size").GetValueAsUnsigned()

    def get_child_at_index(self, index):
        if index == 0:
            return _renamed("[size]", _member(self.valobj, "m_size"))
        if index == 1:
            return _renamed("[capacity]", _member(self.valobj, "m_capacity"))
        begin = _member(self.valobj, "m_begin")
        element = begin.GetType().GetPointeeType()
        address = begin.GetValueAsUnsigned() + (index - 2) * element.GetByteSize()
        return self.valobj.CreateValueFromAddress(f"[{index - 2}]", address, element)


def _optional_value(valobj):
    optional = _object(valobj)
    if not optional.GetChildMemberWithName("m_has_value").GetValueAsUnsigned():
        return None
    value_type = optional.GetType().GetTemplateArgumentType(0)
    storage = optional.GetChildMemberWithName("m_storage")
    return optional.CreateValueFromAddress("[value]", storage.GetLoadAddress(), value_type)


def optional_summary(valobj, internal_dict):
    value = _optional_value(valobj)
    if value is None:
        return "empty"
    return value.GetSummary() or value.GetValue()


class OptionalProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def num_children(self):
        return 0 if _optional_value(self.valobj) is None else 1

    def get_child_at_index(self, index):
        return _optional_value(self.valobj)


class ListProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def _values(self):
        node = _member(self.valobj, "m_head")
        while node.GetValueAsUnsigned():
            node = node.Dereference()
            yield node.GetChildMemberWithName("value")
            node = node.GetChildMemberWithName("next")

    def num_children(self):
        return sum(1 for _ in self._values())

    def get_child_at_index(self, index):
        for i, value in enumerate(self._values()):
            if i == index:
                return _renamed(f"[{i}]", value)
        return None


# the values in key order, named [0], [1], ... like natvis's TreeItems
class IntMapProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def _values(self):
        def in_order(node):
            if node.GetValueAsUnsigned():
                node = node.Dereference()
                yield from in_order(node.GetChildMemberWithName("left"))
                yield node.GetChildMemberWithName("value")
                yield from in_order(node.GetChildMemberWithName("right"))

        return list(in_order(_member(self.valobj, "m_root")))

    def num_children(self):
        return len(self._values())

    def get_child_at_index(self, index):
        return _renamed(f"[{index}]", self._values()[index])


def __lldb_init_module(debugger, internal_dict):
    # The commands run through the command interpreter, so that one that fails fails the import.
    # (debugger.HandleCommand also crashes lldb-dap 23 on Windows.)
    interpreter = debugger.GetCommandInterpreter()

    def add(kind, function, type_name):
        regex = "-x " if "<" in type_name else ""
        option = "-F" if kind == "summary" else "-l"
        result = lldb.SBCommandReturnObject()
        interpreter.HandleCommand(
            f'type {kind} add {regex}{option} {__name__}.{function} "{type_name}"', result
        )
        if not result.Succeeded():
            raise RuntimeError(result.GetError())

    add("summary", "point_summary", "mylib::point")
    add("summary", "string_summary", "mylib::string")
    add("synthetic", "StringProvider", "mylib::string")
    add("summary", "vector_summary", "^mylib::vector<.+>$")
    add("synthetic", "VectorProvider", "^mylib::vector<.+>$")
    add("summary", "optional_summary", "^mylib::optional<.+>$")
    add("synthetic", "OptionalProvider", "^mylib::optional<.+>$")
    add("summary", "list_summary", "^mylib::list<.+>$")
    add("synthetic", "ListProvider", "^mylib::list<.+>$")
    add("summary", "int_map_summary", "^mylib::int_map<.+>$")
    add("synthetic", "IntMapProvider", "^mylib::int_map<.+>$")
