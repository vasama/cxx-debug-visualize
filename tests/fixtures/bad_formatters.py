# lldb formatters that raise while formatting (like bad.natvis and bad_printers.py).
#
# lldb returns an invalid value, without a value, for a missing member; converting that raises.


def pair_summary(valobj, internal_dict):
    a = int(valobj.GetChildMemberWithName("a").GetValue())
    c = int(valobj.GetChildMemberWithName("c").GetValue())  # Pair has no member c
    return f"<{a},{c}>"


def arr_summary(valobj, internal_dict):
    n = valobj.GetNonSyntheticValue().GetChildMemberWithName("n").GetValueAsSigned()
    return f"n={n}"


class ArrProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def num_children(self):
        return int(self.valobj.GetChildMemberWithName("count").GetValue())  # Arr has no count

    def get_child_at_index(self, index):
        data = self.valobj.GetChildMemberWithName("data")
        element = data.GetType().GetPointeeType()
        return data.CreateChildAtOffset(f"[{index}]", index * element.GetByteSize(), element)


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand(f"type summary add -F {__name__}.pair_summary Pair")
    debugger.HandleCommand(f"type summary add -F {__name__}.arr_summary Arr")
    debugger.HandleCommand(f"type synthetic add -l {__name__}.ArrProvider Arr")
