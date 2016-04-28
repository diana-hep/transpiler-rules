from ast import *
execfile("core.py")

def sqr(x, y):
    return x**2 + y

argtype = {"x": "double", "y": "int"}
rettype = "double"

fcndef = Rule("fcndef",
              FunctionDef(Any("name", str), Any("args"), Any("body"), []),
              lambda args, body, name: Block(Format("{0} {1}({2:node}) {{", rettype, name, args), body, Format("}}")))

param = Rule("param",
             Name(Any("name", str), Param()),
             lambda name: Format("{0} {1}", argtype[name], name))

ret = Rule("ret",
           Return(Any("s")),
           lambda s: Return(Format("{0:node};", s)))

pow2 = Rule("pow2",
            BinOp(Any("base"), Pow(), Num(2)),
            lambda base: BinOp(base, Mult(), base))

powN = Rule("powN",
             BinOp(Any("base"), Pow(), Any("exponent")),
             lambda base, exponent: Format("pow({0:node}, {1:node})", base, exponent))

result = Transpiler(sqr, [fcndef, param, ret, pow2, powN]).transform()
print
print "======================================================"
print
print result
print
