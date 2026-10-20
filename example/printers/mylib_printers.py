# gdb pretty printers for the toy types in include/mylib/containers.h; the
# counterpart of natvis/mylib.natvis.

import gdb
import gdb.printing


class PointPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"({int(self.val['x'])}, {int(self.val['y'])})"


class StringPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return self.val["Data"].lazy_string(length=int(self.val["Length"]))

    def display_hint(self):
        return "string"


class VectorPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"size={int(self.val['Size'])}"

    def display_hint(self):
        return "array"

    def children(self):
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
        return f"size={int(self.val['Count'])}"

    def children(self):
        node, i = self.val["Head"], 0
        while node:
            yield f"[{i}]", node["Value"]
            node, i = node["Next"], i + 1


class IntMapPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"size={int(self.val['Count'])}"

    def display_hint(self):
        return "map"

    def children(self):
        # in key order; the "map" hint pairs up keys and values
        def in_order(node):
            if node:
                yield from in_order(node["Left"])
                yield node
                yield from in_order(node["Right"])
        for i, node in enumerate(in_order(self.val["Root"])):
            yield f"key{i}", node["Key"]
            yield f"value{i}", node["Value"]


def build_printers():
    printers = gdb.printing.RegexpCollectionPrettyPrinter("mylib")
    printers.add_printer("Point", "^mylib::Point$", PointPrinter)
    printers.add_printer("String", "^mylib::String$", StringPrinter)
    printers.add_printer("Vector", "^mylib::Vector<.*>$", VectorPrinter)
    printers.add_printer("Optional", "^mylib::Optional<.*>$", OptionalPrinter)
    printers.add_printer("List", "^mylib::List<.*>$", ListPrinter)
    printers.add_printer("IntMap", "^mylib::IntMap<.*>$", IntMapPrinter)
    return printers


gdb.printing.register_pretty_printer(None, build_printers())
