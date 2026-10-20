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

    # the char *, which gdb prints as `0x... "text"`, like natvis's {data_,s8}
    def to_string(self):
        return self.val["data_"]

    def children(self):
        yield "[size]", self.val["length_"]


# natvis also applies a type's visualizer to pointers to it
class StringPointerPrinter(StringPrinter):
    def __init__(self, val):
        super().__init__(val.dereference())


class VectorPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"{{ size={int(self.val['size_'])} }}"

    def children(self):
        yield "[size]", self.val["size_"]
        yield "[capacity]", self.val["capacity_"]
        for i in range(int(self.val["size_"])):
            yield f"[{i}]", (self.val["begin_"] + i).dereference()


class OptionalPrinter:
    def __init__(self, val):
        self.val = val

    def _value(self):
        value_type = self.val.type.strip_typedefs().template_argument(0)
        return self.val["storage_"].address.cast(value_type.pointer()).dereference()

    def to_string(self):
        return self._value() if self.val["has_value_"] else "empty"

    def children(self):
        if self.val["has_value_"]:
            yield "[value]", self._value()


class ListPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"{{ size={int(self.val['count_'])} }}"

    def children(self):
        node, i = self.val["head_"], 0
        while node:
            yield f"[{i}]", node["value"]
            node, i = node["next"], i + 1


class IntMapPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"{{ size={int(self.val['count_'])} }}"

    # the values in key order, named [0], [1], ... like natvis's TreeItems
    def children(self):
        def in_order(node):
            if node:
                yield from in_order(node["left"])
                yield node
                yield from in_order(node["right"])

        for i, node in enumerate(in_order(self.val["root_"])):
            yield f"[{i}]", node["value"]


def build_printers():
    printers = gdb.printing.RegexpCollectionPrettyPrinter("mylib")
    printers.add_printer("point", "^mylib::point$", PointPrinter)
    printers.add_printer("string", "^mylib::string$", StringPrinter)
    printers.add_printer("vector", "^mylib::vector<.*>$", VectorPrinter)
    printers.add_printer("optional", "^mylib::optional<.*>$", OptionalPrinter)
    printers.add_printer("list", "^mylib::list<.*>$", ListPrinter)
    printers.add_printer("int_map", "^mylib::int_map<.*>$", IntMapPrinter)
    return printers


# RegexpCollectionPrettyPrinter only matches a type's own name, so pointers to
# string need a lookup function of their own.
def lookup_string_pointer(val):
    value_type = val.type.strip_typedefs()
    if (
        value_type.code == gdb.TYPE_CODE_PTR
        and str(value_type.target().strip_typedefs()) == "mylib::string"
    ):
        return StringPointerPrinter(val)
    return None


gdb.printing.register_pretty_printer(None, build_printers())
gdb.pretty_printers.append(lookup_string_pointer)
