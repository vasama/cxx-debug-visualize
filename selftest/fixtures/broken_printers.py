# gdb pretty printers that raise while printing (like bad_expr.natvis).

import gdb.printing


class PairPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"<{int(self.val['a'])},{int(self.val['c'])}>"  # Pair has no member c


class ArrPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        return f"n={int(self.val['n'])}"

    def children(self):
        for i in range(int(self.val["count"])):  # Arr has no member count
            yield f"[{i}]", self.val["data"][i]


printers = gdb.printing.RegexpCollectionPrettyPrinter("fixture")
printers.add_printer("Pair", "^Pair$", PairPrinter)
printers.add_printer("Arr", "^Arr$", ArrPrinter)
gdb.printing.register_pretty_printer(None, printers)
