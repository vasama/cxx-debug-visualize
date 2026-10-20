# lldb formatters for the self-test fixture test_program.cpp (like good_printers.py).


def pair_summary(valobj, internal_dict):
    a = valobj.GetChildMemberWithName("a").GetValueAsSigned()
    b = valobj.GetChildMemberWithName("b").GetValueAsSigned()
    return f"<{a},{b}>"


def arr_summary(valobj, internal_dict):
    n = valobj.GetNonSyntheticValue().GetChildMemberWithName("n").GetValueAsSigned()
    return f"n={n}"


class ArrProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def num_children(self):
        return self.valobj.GetChildMemberWithName("n").GetValueAsUnsigned()

    def get_child_at_index(self, index):
        data = self.valobj.GetChildMemberWithName("data")
        element = data.GetType().GetPointeeType()
        return data.CreateChildAtOffset(f"[{index}]", index * element.GetByteSize(), element)


def pair_arr_summary(valobj, internal_dict):
    n = valobj.GetNonSyntheticValue().GetChildMemberWithName("n").GetValueAsSigned()
    return f"pairs={n}"


# the pairs as a map from a to b
class PairArrProvider:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def num_children(self):
        return self.valobj.GetChildMemberWithName("n").GetValueAsUnsigned()

    def get_child_at_index(self, index):
        data = self.valobj.GetChildMemberWithName("data")
        pair_type = data.GetType().GetPointeeType()
        pair = data.CreateChildAtOffset("pair", index * pair_type.GetByteSize(), pair_type)
        key = pair.GetChildMemberWithName("a").GetValueAsSigned()
        b = pair.GetChildMemberWithName("b")
        return b.CreateChildAtOffset(f"[{key}]", 0, b.GetType())


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand(f"type summary add -F {__name__}.pair_summary pair")
    debugger.HandleCommand(f"type summary add -F {__name__}.arr_summary int_array")
    debugger.HandleCommand(f"type synthetic add -l {__name__}.ArrProvider int_array")
    debugger.HandleCommand(f"type summary add -F {__name__}.pair_arr_summary pair_array")
    debugger.HandleCommand(f"type synthetic add -l {__name__}.PairArrProvider pair_array")
