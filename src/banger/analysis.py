"""Conservative source relationships and call-site data flow."""

import re
from collections import deque

from banger.arguments import bind_arguments, omitted_defaults, parameter_names
from banger.expressions import python_reads


class FlowAnalysis:
    def __init__(self, index):
        self.index = index

    def backflow(self, symbol, parameter):
        definition = self.index.get_definition(symbol)
        if parameter not in parameter_names(definition):
            raise ValueError(
                f"Unknown parameter; indexed parameters: {parameter_names(definition)}"
            )
        sites = []
        for call in self.index.get_callers(definition["id"]):
            bindings, binding = bind_arguments(definition, call)
            arguments = bindings.get(parameter, [])
            argument = arguments[0] if len(arguments) == 1 else None
            assignments = self.index.files[call["path"]].get("assignments", [])
            definitions = [
                a
                for a in assignments
                if a["name"] in arguments
                and a["scope"] == call["caller"]
                and a["line"] <= call["line"]
            ]
            sites.append(
                {
                    "caller": call["caller"],
                    "path": call["path"],
                    "line": call["line"],
                    "argument": argument,
                    "arguments": arguments,
                    "binding": binding,
                    "default": omitted_defaults(definition, bindings, binding).get(parameter),
                    "definitions": definitions,
                    "resolution": call["resolution"],
                }
            )
        return {
            "symbol": definition["id"],
            "parameter": parameter,
            "call_sites": sites,
            "graph": self.graph(definition["id"], parameter, reverse=True),
            "scope": "Syntactic argument bindings and preceding assignments; branches, splats and dynamic dispatch may be unresolved",
        }

    def return_uses(self, symbol):
        definition = self.index.get_definition(symbol)
        uses = []
        for call in self.index.get_callers(definition["id"]):
            holder = call.get("holder")
            references = (
                [
                    r
                    for r in self.references(holder)
                    if r["scope"] == call["caller"]
                    and r["path"] == call["path"]
                    and r["line"] >= call["line"]
                ]
                if holder and holder != "$return"
                else []
            )
            uses.append(
                {
                    "caller": call["caller"],
                    "path": call["path"],
                    "line": call["line"],
                    "holder": holder,
                    "references": references,
                    "resolution": call["resolution"],
                }
            )
        return {
            "symbol": definition["id"],
            "uses": uses,
            "scope": "Direct return holders and later name references; does not prove runtime value identity",
        }

    def forwardflow(self, symbol):
        result = self.return_uses(symbol)
        return {**result, "graph": self.graph(result["symbol"], "$return")}

    def references(self, name):
        return [
            r
            for file in self.index.files.values()
            for r in file.get("references", [])
            if r["name"] == name
        ]

    def relevant_tests(self, symbol):
        tree = self.index.call_tree(symbol, reverse=True)
        result = []
        for identity in tree["nodes"]:
            definition = self.index.symbols[identity]
            if definition["name"].startswith("test") or re.search(
                r"(^|/)(tests?|spec)/|[._](test|spec)\.", definition["path"]
            ):
                result.append(definition)
        return result

    def graph(self, symbol, value, reverse=False):
        nodes, edges = {}, []

        def binding_scope(scope, name):
            return self.index.symbols.get(scope, {}).get("python_value_scopes", {}).get(name, scope)

        module_names = {
            path: {
                a["name"]
                for a in [*file.get("assignments", []), *file.get("value_imports", [])]
                if binding_scope(a["scope"], a["name"]) is None
            }
            for path, file in self.index.files.items()
        }

        def variable(scope, name, path=None):
            path = self.index.symbols[scope]["path"] if scope else path
            scope = binding_scope(scope, name)
            identity = f"{scope or 'module|' + path}|value|{name}"
            nodes[identity] = {"id": identity, "symbol": scope, "name": name, "path": path}
            return identity

        def expression(scope, content, path, line):
            identity = f"{scope or 'module|' + path}|expression|{line}|{content}"
            nodes[identity] = {
                "id": identity,
                "symbol": scope,
                "expression": content,
                "path": path,
                "line": line,
            }
            # Limit reads to known bindings; other languages retain lexical approximation.
            owner = self.index.symbols.get(scope, {})
            names = set(parameter_names(owner) + owner.get("bindings", []))
            if "python_value_scopes" in owner:
                names = {
                    name
                    for name, target in owner["python_value_scopes"].items()
                    if target is not None or name in module_names.get(path, set())
                }
            if scope is None:
                names.update(module_names.get(path, set()))
            reads = (
                python_reads(content)
                if path.endswith(".py")
                else set(re.findall(r"\b[A-Za-z_]\w*\b", content))
            )
            for name in sorted(reads):
                if name in names:
                    edges.append(
                        {
                            "source": variable(scope, name, path),
                            "target": identity,
                            "evidence": "syntactic expression dependency",
                        }
                    )
            return identity

        for path, file in self.index.files.items():
            for imported in file.get("value_imports", []):
                module = imported["module"].replace(".", "/")
                candidates = sorted(
                    {
                        prefix + module + suffix
                        for prefix in ("", "src/")
                        for suffix in (".py", "/__init__.py")
                        if prefix + module + suffix in self.index.files
                    }
                )
                for candidate in candidates:
                    if imported["member"] not in module_names.get(candidate, set()):
                        continue
                    edges.append(
                        {
                            "source": variable(None, imported["member"], candidate),
                            "target": variable(imported["scope"], imported["name"], path),
                            "kind": "import binding",
                            "evidence": "syntactic project from-import binding",
                            "resolution": "resolved" if len(candidates) == 1 else "ambiguous",
                            "candidates": candidates,
                            "path": path,
                            "line": imported["line"],
                        }
                    )
            for assignment in file.get("assignments", []):
                source = expression(
                    assignment["scope"],
                    assignment["expression"],
                    assignment["path"],
                    assignment["line"],
                )
                edges.append(
                    {
                        "source": source,
                        "target": variable(
                            assignment["scope"], assignment["name"], assignment["path"]
                        ),
                        "evidence": "assignment dependency",
                    }
                )
            for returned in file.get("returns", []):
                source = expression(
                    returned["scope"], returned["expression"], returned["path"], returned["line"]
                )
                edges.append(
                    {
                        "source": source,
                        "target": variable(returned["scope"], "$return", returned["path"]),
                        "evidence": "return dependency",
                    }
                )
        for call in self.index.calls:
            for target in call["targets"]:
                bindings, binding = bind_arguments(self.index.symbols[target], call)
                defaults = omitted_defaults(self.index.symbols[target], bindings, binding)
                for param, origin in defaults.items():
                    identity = f"{target}|default|{param}"
                    if identity not in nodes:
                        source = expression(
                            origin["scope"],
                            origin["expression"],
                            origin["path"],
                            origin["line"],
                        )
                        edges.append(
                            {
                                "source": source,
                                "target": identity,
                                "evidence": "syntactic declaration-scope dependency",
                                "kind": "default expression",
                            }
                        )
                    nodes[identity] = {
                        "id": identity,
                        "symbol": origin["scope"],
                        "expression": origin["expression"],
                        "path": origin["path"],
                        "line": origin["line"],
                    }
                    edges.append(
                        {
                            "source": identity,
                            "target": variable(target, param),
                            "evidence": call["resolution"],
                            "kind": "default argument",
                            "binding": "declared default origin; runtime object may have changed",
                        }
                    )
                for param, arguments in bindings.items():
                    for content in arguments:
                        source = expression(call["caller"], content, call["path"], call["line"])
                        edges.append(
                            {
                                "source": source,
                                "target": variable(target, param),
                                "evidence": call["resolution"],
                                "binding": binding,
                                "kind": "call argument",
                            }
                        )
                if call.get("holder"):
                    edges.append(
                        {
                            "source": variable(target, "$return"),
                            "target": variable(call["caller"], call["holder"], call["path"]),
                            "evidence": call["resolution"],
                            "kind": "call return",
                        }
                    )
        start = variable(symbol, value)
        adjacency = {}
        for edge in edges:
            adjacency.setdefault(edge["target"] if reverse else edge["source"], []).append(edge)
        queue, seen, selected = deque([start]), {start}, []
        truncated = False
        while queue:
            current = queue.popleft()
            for edge in adjacency.get(current, []):
                following = edge["source"] if reverse else edge["target"]
                if following not in seen:
                    if len(seen) >= 1000:
                        truncated = True
                        continue
                    seen.add(following)
                    queue.append(following)
                selected.append(edge)
        return {
            "nodes": [nodes[n] for n in sorted(seen)],
            "edges": selected,
            "truncated": truncated,
            "scope": "Conservative, path-insensitive dependency graph; ambiguous call candidates remain marked",
        }
