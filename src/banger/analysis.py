"""Conservative source relationships and call-site data flow."""

import re
from collections import deque

from banger.arguments import bind_arguments, parameter_names


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

        def variable(scope, name):
            identity = f"{scope}|value|{name}"
            nodes[identity] = {"id": identity, "symbol": scope, "name": name}
            return identity

        def expression(scope, content, path, line):
            identity = f"{scope}|expression|{line}|{content}"
            nodes[identity] = {
                "id": identity,
                "symbol": scope,
                "expression": content,
                "path": path,
                "line": line,
            }
            # Match only names already known as locals or parameters, avoiding calls/types/keywords.
            owner = self.index.symbols.get(scope, {})
            names = set(parameter_names(owner) + owner.get("bindings", []))
            for name in re.findall(r"\b[A-Za-z_]\w*\b", content):
                if name in names:
                    edges.append(
                        {
                            "source": variable(scope, name),
                            "target": identity,
                            "evidence": "syntactic expression dependency",
                        }
                    )
            return identity

        for file in self.index.files.values():
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
                        "target": variable(assignment["scope"], assignment["name"]),
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
                        "target": variable(returned["scope"], "$return"),
                        "evidence": "return dependency",
                    }
                )
        for call in self.index.calls:
            for target in call["targets"]:
                bindings, binding = bind_arguments(self.index.symbols[target], call)
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
                            "target": variable(call["caller"], call["holder"]),
                            "evidence": call["resolution"],
                            "kind": "call return",
                        }
                    )
        start = variable(symbol, value)
        adjacency = {}
        for edge in edges:
            adjacency.setdefault(edge["target"] if reverse else edge["source"], []).append(edge)
        queue, seen, selected = deque([start]), {start}, []
        while queue and len(seen) < 1000:
            current = queue.popleft()
            for edge in adjacency.get(current, []):
                selected.append(edge)
                following = edge["source"] if reverse else edge["target"]
                if following not in seen:
                    seen.add(following)
                    queue.append(following)
        return {
            "nodes": [nodes[n] for n in sorted(seen)],
            "edges": selected,
            "truncated": bool(queue),
            "scope": "Conservative, path-insensitive dependency graph; ambiguous call candidates remain marked",
        }
