"""C++ lexical ancestry; preprocessing and include visibility remain unproven."""

import re

from banger.bindings import node_text


def declaration_scope(node):
    scope = []
    uncertain = False
    parent = node.parent
    while parent:
        if parent.type in {"namespace_definition", "class_specifier", "struct_specifier"}:
            name = node_text(parent.child_by_field_name("name"))
            # Anonymous namespaces must not merge into the global namespace.
            scope.append(name or f"(anonymous:{parent.start_byte})")
        elif parent.type in {"function_definition", "lambda_expression", "compound_statement"}:
            scope.append(f"(local:{parent.start_byte})")
        if parent.type.startswith("preproc_if") or parent.type == "template_declaration":
            uncertain = True
        parent = parent.parent
    return {
        "cpp_scope": "::".join(reversed(scope)),
        "cpp_start": node.start_byte,
        "cpp_end": node.end_byte,
        "cpp_complete": node.child_by_field_name("body") is not None,
        "cpp_uncertain": uncertain,
    }


def type_bindings(tree):
    bindings = []
    stack = [tree]
    while stack:
        node = stack.pop()
        stack.extend(node.named_children)
        if node.type not in {
            "alias_declaration",
            "type_definition",
            "using_declaration",
            "namespace_alias_definition",
            "namespace_definition",
        }:
            continue
        if node.type == "using_declaration":
            name = (
                "*"
                if any(c.type == "namespace" for c in node.children)
                else node_text(node.named_children[-1]).split("::")[-1]
            )
        else:
            name = node_text(
                node.child_by_field_name("name") or node.child_by_field_name("declarator")
            )
        bindings.append(
            {
                "name": name.split("::")[0],
                "scope": declaration_scope(node)["cpp_scope"],
                "end": node.start_byte if node.type == "namespace_definition" else node.end_byte,
                "namespace": node.type == "namespace_definition",
            }
        )
    return bindings


def base_link(definition, expression, classes, bindings):
    expression_name = re.sub(r"\s*::\s*", "::", expression)
    result = {"expression": expression, "targets": [], "resolution": "unknown"}
    if not re.fullmatch(r"(?:::)?[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", expression_name):
        return {**result, "evidence": "template or computed C++ base expression; not resolved"}
    scope = definition["cpp_scope"].split("::") if definition["cpp_scope"] else []
    if expression_name.startswith("::"):
        lookups = [("", expression_name[2:])]
    else:
        lookups = [
            ("::".join(scope[:depth]), "::".join(scope[:depth] + [expression_name]))
            for depth in range(len(scope), -1, -1)
        ]
    by_name = {}
    for symbol in classes:
        if symbol["language"] != "cpp" or symbol["id"] == definition["id"]:
            continue
        name = "::".join(filter(None, [symbol["cpp_scope"], symbol["name"]]))
        by_name.setdefault(name, []).append(symbol)

    for lookup_scope, name in lookups:
        matching_bindings = [
            b
            for b in bindings
            if b["scope"] == lookup_scope
            and b["end"] <= definition["cpp_start"]
            and b["name"] in {"*", expression_name.lstrip(":").split("::")[0]}
        ]
        if any(not b["namespace"] for b in matching_bindings):
            return {
                **result,
                "evidence": "C++ alias or using binding requires expansion; not resolved",
            }
        local = [
            s
            for s in by_name.get(name, [])
            if s["path"] == definition["path"] and s["cpp_end"] <= definition["cpp_start"]
        ]
        if local:
            complete = [s for s in local if s["cpp_complete"]]
            candidates = complete or local
            proven = (
                len(complete) == 1
                and not complete[0]["cpp_uncertain"]
                and not definition["cpp_uncertain"]
            )
            return {
                **result,
                "targets": [s["id"] for s in candidates],
                "resolution": "resolved" if proven else "ambiguous",
                "evidence": "preceding class definition in nearest C++ lexical scope"
                if proven
                else "incomplete, conditional, template or duplicate C++ declaration",
            }
        if matching_bindings:
            return {
                **result,
                "evidence": "nearest C++ namespace has no visible indexed base definition",
            }
    candidates = [s for _, name in lookups for s in by_name.get(name, [])]
    return {
        **result,
        "targets": [s["id"] for s in candidates],
        "resolution": "ambiguous" if candidates else "unknown",
        "evidence": "qualified C++ name candidates; include visibility or declaration order not proven",
    }
