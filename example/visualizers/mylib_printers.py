# gdb pretty printers for the toy types in include/mylib/containers.hpp; the
# counterpart of mylib.natvis, written so that the Visual Studio debug adapter
# shows the same trees with either.

import gdb
import gdb.printing


class PointPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"({int(self.val['x'])}, {int(self.val['y'])})"

    # natvis shows the members of a type without <Expand>
    def children(self):
        yield "x", self.val["x"]
        yield "y", self.val["y"]


class StringPrinter:
    def __init__(self, val):
        self.val = val

    # the char *, which gdb prints as `0x... "text"`, like natvis's {Data,s8}
    def to_string(self):
        return self.val["Data"]

    def children(self):
        yield "[size]", self.val["Length"]


# natvis also applies a type's visualizer to pointers to it
class StringPointerPrinter(StringPrinter):
    def __init__(self, val):
        super().__init__(val.dereference())


class VectorPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"{{ size={int(self.val['Size'])} }}"

    def children(self):
        yield "[size]", self.val["Size"]
        yield "[capacity]", self.val["Capacity"]
        for i in range(int(self.val["Size"])):
            yield f"[{i}]", (self.val["Begin"] + i).dereference()


class OptionalPrinter:
    def __init__(self, val):
        self.val = val

    def _value(self):
        value_type = self.val.type.strip_typedefs().template_argument(0)
        return self.val["Storage"].address.cast(value_type.pointer()).dereference()

    def to_string(self):
        return self._value() if self.val["HasValue"] else "empty"

    def children(self):
        if self.val["HasValue"]:
            yield "[value]", self._value()


class ListPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"{{ size={int(self.val['Count'])} }}"

    def children(self):
        node, i = self.val["Head"], 0
        while node:
            yield f"[{i}]", node["Value"]
            node, i = node["Next"], i + 1


class IntMapPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"{{ size={int(self.val['Count'])} }}"

    # the values in key order, named [0], [1], ... like natvis's TreeItems
    def children(self):
        def in_order(node):
            if node:
                yield from in_order(node["Left"])
                yield node
                yield from in_order(node["Right"])

        for i, node in enumerate(in_order(self.val["Root"])):
            yield f"[{i}]", node["Value"]


def build_printers():
    printers = gdb.printing.RegexpCollectionPrettyPrinter("mylib")
    printers.add_printer("Point", "^mylib::Point$", PointPrinter)
    printers.add_printer("String", "^mylib::String$", StringPrinter)
    printers.add_printer("Vector", "^mylib::Vector<.*>$", VectorPrinter)
    printers.add_printer("Optional", "^mylib::Optional<.*>$", OptionalPrinter)
    printers.add_printer("List", "^mylib::List<.*>$", ListPrinter)
    printers.add_printer("IntMap", "^mylib::IntMap<.*>$", IntMapPrinter)
    return printers


# RegexpCollectionPrettyPrinter only matches a type's own name, so pointers to
# String need a lookup function of their own.
def lookup_string_pointer(val):
    value_type = val.type.strip_typedefs()
    if (
        value_type.code == gdb.TYPE_CODE_PTR
        and str(value_type.target().strip_typedefs()) == "mylib::String"
    ):
        return StringPointerPrinter(val)
    return None


gdb.printing.register_pretty_printer(None, build_printers())
gdb.pretty_printers.append(lookup_string_pointer)
