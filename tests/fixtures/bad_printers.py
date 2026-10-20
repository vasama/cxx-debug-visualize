# gdb pretty printers that raise while printing (like bad.natvis).

import gdb.printing


class PairPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"<{int(self.val['a'])},{int(self.val['c'])}>"  # pair has no member c


class ArrPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"n={int(self.val['n'])}"

    def children(self):
        for i in range(int(self.val["count"])):  # int_array has no member count
            yield f"[{i}]", self.val["data"][i]


printers = gdb.printing.RegexpCollectionPrettyPrinter("fixture")
printers.add_printer("pair", "^pair$", PairPrinter)
printers.add_printer("int_array", "^int_array$", ArrPrinter)
gdb.printing.register_pretty_printer(None, printers)
