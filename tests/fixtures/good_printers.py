# gdb pretty printers for the self-test fixture test_program.cpp.

import gdb.printing


class PairPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"<{int(self.val['a'])},{int(self.val['b'])}>"


class ArrPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"n={int(self.val['n'])}"

    def display_hint(self):
        return "array"

    def children(self):
        for i in range(int(self.val["n"])):
            yield f"[{i}]", self.val["data"][i]


# the pairs as a map from a to b
class PairArrPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"pairs={int(self.val['n'])}"

    def display_hint(self):
        return "map"

    def children(self):
        for i in range(int(self.val["n"])):
            yield f"key{i}", self.val["data"][i]["a"]
            yield f"value{i}", self.val["data"][i]["b"]


printers = gdb.printing.RegexpCollectionPrettyPrinter("fixture")
printers.add_printer("Pair", "^Pair$", PairPrinter)
printers.add_printer("Arr", "^Arr$", ArrPrinter)
printers.add_printer("PairArr", "^PairArr$", PairArrPrinter)
gdb.printing.register_pretty_printer(None, printers)
