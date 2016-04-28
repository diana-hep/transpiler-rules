#!/usr/bin/env python

# Copyright 2016 Jim Pivarski
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ast
import sys
import types

import meta.decompiler
import meta.asttools
import meta.asttools.visitors.pysourcegen

class Block(ast.AST):
    def __init__(self, before, body, after, indent=True):
        self.before = before
        self.body = body
        self.after = after
        self.indent = indent
        self._fields = ("before", "body", "after",)

def visitBlock(self, node):
    p = getattr(self, "print")
    if node.before is not None:
        self.visit(node.before)
    if node.indent:
        with self.indenter:
            for b in node.body:
                self.visit(b)
    else:
        with self.no_indent:
            for b in node.body:
                self.visit(b)
    if node.after is not None:
        self.visit(node.after)

class Format(ast.AST):
    def __init__(self, formatter, *args):
        self.formatter = formatter
        self.args = args
        self._fields = ("formatter",)

def visitFormat(self, node):
    p = getattr(self, "print")
    p(node.formatter, *node.args)

meta.asttools.visitors.pysourcegen.SourceGen.visitBlock = \
    types.MethodType(visitBlock, None, meta.asttools.visitors.pysourcegen.SourceGen)

meta.asttools.visitors.pysourcegen.ExprSourceGen.visitBlock = \
    types.MethodType(visitBlock, None, meta.asttools.visitors.pysourcegen.ExprSourceGen)

meta.asttools.visitors.pysourcegen.SourceGen.visitFormat = \
    types.MethodType(visitFormat, None, meta.asttools.visitors.pysourcegen.SourceGen)

meta.asttools.visitors.pysourcegen.ExprSourceGen.visitFormat = \
    types.MethodType(visitFormat, None, meta.asttools.visitors.pysourcegen.ExprSourceGen)

class TranspilerException(Exception):
    pass

class Transpiler(object):
    def __init__(self, func, rules=[]):
        if isinstance(func, basestring):
            parsed = ast.parse(func)

            if len(parsed.body) == 1 and isinstance(parsed.body[0], ast.FunctionDef):
                g = {}
                exec(compile(parsed, "<string>", "exec"), g)
                self.func = g[parsed.body[0].name]
                self.ast = parsed.body[0]

            elif len(parsed.body) == 1 and isinstance(parsed.body[0], ast.Expr) and isinstance(parsed.body[0].value, ast.Lambda):
                self.func = eval(compile(func, "<string>", "eval"))
                self.ast = parsed.body[0].value

            else:
                raise TranspilerException("{} does not compile to a function".format(self.func))

        else:
            self.func = func
            self.ast = meta.decompiler.decompile_func(func)

        self.rules = list(rules)

    def __repr__(self):
        return "Transpiler({})".format(self.func)

    def tree(self, stream=sys.stdout):
        if stream is None:
            return meta.asttools.str_ast(self.ast, " ", "\n").strip("\n")
        else:
            meta.asttools.print_ast(self.ast, " ", 0, "\n", stream)

    def python(self, stream=sys.stdout):
        if stream is None:
            return meta.asttools.dump_python_source(self.ast)
        else:
            meta.asttools.python_source(self.ast, stream)

    def transform(self, var={}, verbose=True):
        matched = _upwardRecursion(var, verbose, self.ast, self.rules, [])
        return _tostring(matched)
        
def _tostring(node):
    return meta.asttools.dump_python_source(node).lstrip("\n")

def _upwardRecursion(var, verbose, node, rules, trail):
    if isinstance(node, ast.AST):
        # upward recursion, looking for partial matches
        submatches = dict(node.__dict__)
        for field in node._fields:
            submatches[field] = _upwardRecursion(var, verbose, getattr(node, field), rules, trail + ["." + field])
        out = node.__class__(**submatches)

        matches = filter(lambda x: x is not None, [rule.match(out) for rule in rules])

        if verbose:
            if isinstance(node, ast.AST):
                name = node.__class__.__name__
            elif isinstance(node, list):
                name = "(list)"
            elif isinstance(node, tuple):
                name = "(tuple)"
            elif isinstance(node, dict):
                name = "(dict)"
            else:
                name = repr(node)
            prefix = "{:50s} {:15s} ".format("".join(trail), name)
            if len(matches) == 0:
                sys.stdout.write(prefix + "\n")
            else:
                first = True
                for match in matches:
                    if first:
                        sys.stdout.write(prefix)
                        first = False
                    else:
                        sys.stdout.write(" " * len(prefix))
                    sys.stdout.write(match.rule.name + ": " + repr(_tostring(out)) + " -> " + repr(_tostring(match.transform(var))) + "\n")

        if len(matches) > 0:
            return matches[0].transform(var)
        else:
            return out

    elif isinstance(node, (list, tuple)):
        # upward recursion, looking for partial matches
        out = []
        for i, x in enumerate(node):
            out.append(_upwardRecursion(var, verbose, x, rules, trail + ["[" + str(i) + "]"]))
        return out

    elif isinstance(node, dict):
        # upward recursion, looking for partial matches
        out = {}
        for k, v in node.items():
            out[k] = _upwardRecursion(var, verbose, v, rules, trail + ["[" + repr(k) + "]"])
        return out

    else:
        return node

# downward recursion, looking for a complete match
def _downwardRecursion(pattern, target, refs):
    if isinstance(pattern, ast.AST) and isinstance(target, ast.AST):
        if pattern.__class__ == target.__class__:
            return all(_downwardRecursion(getattr(pattern, field), getattr(target, field), refs) for field in pattern._fields)
        else:
            return False

    elif isinstance(pattern, Pattern):
        return pattern.matches(target, refs)

    elif isinstance(pattern, (list, tuple)) and isinstance(target, (list, tuple)):
        if len(pattern) == len(target):
            return all(_downwardRecursion(x, y, refs) for x, y in zip(pattern, target))
        else:
            return False

    elif isinstance(pattern, dict) and isinstance(target, dict):
        if set(pattern.keys()) == set(target.keys()):
            return all(_downwardRecursion(pattern[k], target[k], refs) for k in pattern.keys())
        else:
            return False

    else:
        return pattern == target

class Pattern(object):
    pass

class Any(Pattern):
    def __init__(self, ref, *types):
        self.ref = ref
        self.types = types

    def matches(self, node, refs):
        if len(self.types) > 0:
            out = isinstance(node, self.types)
        else:
            out = True
        if out:
            refs[self.ref] = node
        return out

class Match(object):
    def __init__(self, rule, node, refs):
        self.rule = rule
        self.node = node
        self.refs = refs

    def __repr__(self):
        if isinstance(node, ast.AST):
            name = node.__class__.__name__
        elif isinstance(node, list):
            name = "(list)"
        elif isinstance(node, tuple):
            name = "(tuple)"
        elif isinstance(node, dict):
            name = "(dict)"
        else:
            name = repr(node)
        return "Match({}, {}, {})".format(self.rule.name, name, repr(self.refs))

    def transform(self, var):
        return self.rule.transform(dict(self.refs, **var))

class Rule(object):
    def __init__(self, name, pattern, to):
        self.name = name
        self.pattern = pattern
        self.to = to

    def __repr__(self):
        return "Rule({}, {}, {})".format(self.name, self.pattern, repr(self.to))

    def match(self, node):
        refs = {}
        if _downwardRecursion(self.pattern, node, refs):
            return Match(self, node, refs)
        else:
            return None

    def transform(self, var):
        return self.to(**var)
