from ast import *
execfile("core.py")

def sqr(x, y):
    return x**2 + y

fcndef = Rule("fcndef",
              FunctionDef(Any("name", str), Any("args"), Any("body"), []),
              lambda args, body, name: Block(Format("double {0}({1:node}) {{", name, args), body, Format("}}")))

param = Rule("param",
             Name(Any("name", str), Param()),
             lambda name: Format("double {0}", name))

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
