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

import meta.decompiler
import meta.asttools

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
            return meta.asttools.str_ast(self.ast, " ", "\n")
        else:
            meta.asttools.print_ast(self.ast, " ", 0, "\n", stream)

    def python(self, stream=sys.stdout):
        if stream is None:
            return meta.asttools.dump_python_source(self.ast)
        else:
            meta.asttools.python_source(self.ast, stream)

    def transform(self, var={}, stream=sys.stdout):
        matches = self.match(False, self.ast)
        if len(matches) == 1:
            result = matches[0].transform(var, 0)
            if stream is None:
                return result
            else:
                stream.write(result)

        elif len(matches) == 0:
            raise TranspilerException("no rules matched the function; try calling .match(verbose=True)")

        else:
            raise TranspilerException("top level is ambiguous; the following rules match: " + ", ".join(rule.name for rule in matches))

    def match(self, verbose=True, stream=sys.stdout):
        return self._match(verbose, self.ast, [], stream)

    def _match(self, verbose, node, trail, stream):
        submatches = {}

        # upward recursion, looking for partial matches
        if isinstance(node, ast.AST):
            for field in node._fields:
                submatches[field] = self._match(verbose, getattr(node, field), trail + ["." + field], stream)

        elif isinstance(node, (list, tuple)):
            for i, x in enumerate(node):
                submatches[i] = self._match(verbose, x, trail + ["[" + str(i) + "]"], stream)

        elif isinstance(node, dict):
            for k, v in node.items():
                submatches[k] = self._match(verbose, v, trail + ["[" + repr(k) + "]"], stream)

        results = []
        for rule in self.rules:
            for match in rule.matches(node):
                results.append(match)

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
            stream.write("{:50s} {:15s} {}\n".format("".join(trail), name, ", ".join(map(repr, results)) if len(results) > 0 else "(nothing)"))

        return results

# downward recursion, looking for a complete match
def matches(pattern, target, refs):
    if isinstance(pattern, ast.AST) and isinstance(target, ast.AST):
        if pattern.__class__ == target.__class__:
            return all(matches(getattr(pattern, field), getattr(target, field), refs) for field in pattern._fields)
        else:
            return False

    elif isinstance(pattern, Pattern):
        return pattern.matches(target, refs)

    elif isinstance(pattern, (list, tuple)) and isinstance(target, (list, tuple)):
        if len(pattern) == len(target):
            return all(matches(x, y, refs) for x, y in zip(pattern, target))
        else:
            return False

    elif isinstance(pattern, dict) and isinstance(target, dict):
        if set(pattern.keys()) == set(target.keys()):
            return all(matches(pattern[k], target[k], refs) for k in pattern.keys())
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
    def __init__(self, rule, refs):
        self.rule = rule
        self.refs = refs

    def __repr__(self):
        return self.rule.name + "(" + repr(self.refs) + ")"

class Rule(object):
    def __init__(self, name, pattern):
        self.name = name
        self.pattern = pattern

    def __repr__(self):
        return "Rule({}, {}, {})".format(self.name, self.pattern, repr(self.format))

    def matches(self, node):
        refs = {}
        if matches(self.pattern, node, refs):
            yield Match(self, refs)
        
