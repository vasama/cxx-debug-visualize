# lldb formatters for the toy types in include/mylib/containers.h; the
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


# the char *, as `0x... "text"`, like natvis's {Data,s8}
def string_summary(valobj, internal_dict):
    data = _member(valobj, "Data")
    return f"{data.GetValue()} {data.GetSummary()}"


class StringProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def num_children(self):
        return 1

    def get_child_at_index(self, index):
        return _renamed("[size]", _member(self.valobj, "Length"))


# `{ size=N }`, N being the value of the member `member`
def size_summary(member):
    def summary(valobj, internal_dict):
        return f"{{ size={_member(valobj, member).GetValueAsUnsigned()} }}"
    return summary


vector_summary = size_summary("Size")
list_summary = size_summary("Count")
int_map_summary = size_summary("Count")


class VectorProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def num_children(self):
        return 2 + _member(self.valobj, "Size").GetValueAsUnsigned()

    def get_child_at_index(self, index):
        if index == 0:
            return _renamed("[size]", _member(self.valobj, "Size"))
        if index == 1:
            return _renamed("[capacity]", _member(self.valobj, "Capacity"))
        begin = _member(self.valobj, "Begin")
        element = begin.GetType().GetPointeeType()
        address = begin.GetValueAsUnsigned() + (index - 2) * element.GetByteSize()
        return self.valobj.CreateValueFromAddress(f"[{index - 2}]", address, element)


def _optional_value(valobj):
    optional = _object(valobj)
    if not optional.GetChildMemberWithName("HasValue").GetValueAsUnsigned():
        return None
    value_type = optional.GetType().GetTemplateArgumentType(0)
    storage = optional.GetChildMemberWithName("Storage")
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
        node = _member(self.valobj, "Head")
        while node.GetValueAsUnsigned():
            node = node.Dereference()
            yield node.GetChildMemberWithName("Value")
            node = node.GetChildMemberWithName("Next")

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
                yield from in_order(node.GetChildMemberWithName("Left"))
                yield node.GetChildMemberWithName("Value")
                yield from in_order(node.GetChildMemberWithName("Right"))
        return list(in_order(_member(self.valobj, "Root")))

    def num_children(self):
        return len(self._values())

    def get_child_at_index(self, index):
        return _renamed(f"[{index}]", self._values()[index])


def __lldb_init_module(debugger, internal_dict):
    def add(kind, function, type_name):
        regex = "-x " if "<" in type_name else ""
        option = "-F" if kind == "summary" else "-l"
        debugger.HandleCommand(f'type {kind} add {regex}{option} {__name__}.{function} '
                               f'"{type_name}"')

    add("summary", "point_summary", "mylib::Point")
    add("summary", "string_summary", "mylib::String")
    add("synthetic", "StringProvider", "mylib::String")
    add("summary", "vector_summary", "^mylib::Vector<.+>$")
    add("synthetic", "VectorProvider", "^mylib::Vector<.+>$")
    add("summary", "optional_summary", "^mylib::Optional<.+>$")
    add("synthetic", "OptionalProvider", "^mylib::Optional<.+>$")
    add("summary", "list_summary", "^mylib::List<.+>$")
    add("synthetic", "ListProvider", "^mylib::List<.+>$")
    add("summary", "int_map_summary", "^mylib::IntMap<.+>$")
    add("synthetic", "IntMapProvider", "^mylib::IntMap<.+>$")
