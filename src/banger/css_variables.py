"""Bounded substitution for the statically supported CSS variable syntax."""

import re


class CSSVariables:
    def __init__(self, values):
        self.values = values
        self.resolved = {}
        self.invalid = set()
        visited = set()

        def visit(name, path):
            if name in path:
                self.invalid.update(path[path.index(name) :])
                return
            if name in visited or name not in values:
                return
            if len(path) >= 64:
                self.invalid.update(path)
                return
            for dependency in re.findall(r"var\(\s*(--[\w-]+)", values[name]):
                visit(dependency, [*path, name])
            visited.add(name)

        for name in values:
            visit(name, [])

    def resolve(self, name, depth=0):
        if depth >= 64 or name in self.invalid:
            raise ValueError("Cyclic or unsupported CSS variable dependency: " + name)
        if name not in self.values:
            raise ValueError("Undefined CSS variable " + name)
        if name not in self.resolved:
            try:
                self.resolved[name] = self.substitute(self.values[name], depth + 1)
            except ValueError:
                self.invalid.add(name)
                raise
        return self.resolved[name]

    def substitute(self, value, depth=0):
        pattern = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*))?\)")
        if "var(" in value and any(quote in value for quote in ('"', "'")):
            raise ValueError("Quoted CSS variable expressions are not statically evaluated")
        for _ in range(20):
            match = pattern.search(value)
            if not match:
                if "var(" in value:
                    raise ValueError("Nested or unsupported CSS variable expression")
                return value
            name, fallback = match.groups()
            try:
                replacement = self.resolve(name, depth)
            except ValueError:
                if fallback is None:
                    raise
                replacement = self.substitute(fallback, depth + 1)
            value = value[: match.start()] + replacement + value[match.end() :]
            if len(value) > 50000:
                raise ValueError("CSS variable expansion exceeds the static analysis limit")
        raise ValueError("CSS variable substitution limit reached")
