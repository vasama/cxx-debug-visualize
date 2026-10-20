# lldb formatters for the toy types in include/mylib/containers.hpp; the
# counterpart of mylib.natvis and mylib_printers.py, written so
# that lldb shows the same trees as far as it can.
#
# Loaded with `command script import`, which calls __lldb_init_module.


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


# the char *, as `0x... "text"`, like natvis's {data_,s8}
def string_summary(valobj, internal_dict):
    data = _member(valobj, "data_")
    return f"{data.GetValue()} {data.GetSummary()}"


class StringProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def num_children(self):
        return 1

    def get_child_at_index(self, index):
        return _renamed("[size]", _member(self.valobj, "length_"))


# `{ size=N }`, N being the value of the member `member`
def size_summary(member):
    def summary(valobj, internal_dict):
        return f"{{ size={_member(valobj, member).GetValueAsUnsigned()} }}"

    return summary


vector_summary = size_summary("size_")
list_summary = size_summary("count_")
int_map_summary = size_summary("count_")


class VectorProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def num_children(self):
        return 2 + _member(self.valobj, "size_").GetValueAsUnsigned()

    def get_child_at_index(self, index):
        if index == 0:
            return _renamed("[size]", _member(self.valobj, "size_"))
        if index == 1:
            return _renamed("[capacity]", _member(self.valobj, "capacity_"))
        begin = _member(self.valobj, "begin_")
        element = begin.GetType().GetPointeeType()
        address = begin.GetValueAsUnsigned() + (index - 2) * element.GetByteSize()
        return self.valobj.CreateValueFromAddress(f"[{index - 2}]", address, element)


def _optional_value(valobj):
    optional = _object(valobj)
    if not optional.GetChildMemberWithName("has_value_").GetValueAsUnsigned():
        return None
    value_type = optional.GetType().GetTemplateArgumentType(0)
    storage = optional.GetChildMemberWithName("storage_")
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
        node = _member(self.valobj, "head_")
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

        return list(in_order(_member(self.valobj, "root_")))

    def num_children(self):
        return len(self._values())

    def get_child_at_index(self, index):
        return _renamed(f"[{index}]", self._values()[index])


def __lldb_init_module(debugger, internal_dict):
    def add(kind, function, type_name):
        regex = "-x " if "<" in type_name else ""
        option = "-F" if kind == "summary" else "-l"
        debugger.HandleCommand(
            f'type {kind} add {regex}{option} {__name__}.{function} "{type_name}"'
        )

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
