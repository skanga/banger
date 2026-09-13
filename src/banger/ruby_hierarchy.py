"""Ruby constant ancestry; runtime loading and metaprogramming remain unproven."""

import re

from banger.bindings import node_text


def constant_path(value):
    return bool(re.fullmatch(r"(?:::)?[A-Z]\w*(?:::[A-Z]\w*)*", value))


def lookup_names(expression, nesting):
    if expression.startswith("::"):
        return [expression[2:]]
    return ["::".join(filter(None, [scope, expression])) for scope in [*nesting, ""]]


def annotate(tree, symbols):
    bindings = []
    declarations = {(s["line"], s["name"]): s for s in symbols if s["kind"] == "class"}

    def visit(node, nesting=(), uncertain=False):
        if (
            node.type == "call"
            and nesting
            and node_text(node.child_by_field_name("method"))
            in {
                "include",
                "prepend",
                "extend",
            }
        ):
            for binding in bindings:
                if binding["name"] == nesting[0]:
                    binding["ancestors"] = True
        if node.type in {"class", "module", "assignment", "operator_assignment"}:
            name = node_text(node.child_by_field_name("name") or node.child_by_field_name("left"))
            if constant_path(name):
                qualified = lookup_names(name, nesting)[0]
                if "::" in name and not name.startswith("::"):
                    prefix = name.split("::")[0]
                    visible = next(
                        (
                            n
                            for n in lookup_names(prefix, nesting)
                            if any(b["name"] == n for b in bindings)
                        ),
                        None,
                    )
                    if visible:
                        qualified = visible + name[len(prefix) :]
                    else:
                        uncertain = True
                binding = {
                    "name": qualified,
                    "kind": node.type,
                    "start": node.start_byte,
                    "uncertain": uncertain,
                    "ancestors": node.child_by_field_name("superclass") is not None,
                }
                bindings.append(binding)
                if node.type == "class":
                    symbol = declarations.get((node.start_point.row + 1, name))
                    if symbol:
                        superclass = node.child_by_field_name("superclass")
                        symbol.update(
                            ruby_name=qualified,
                            ruby_nesting=list(nesting),
                            ruby_start=node.start_byte,
                            ruby_uncertain=uncertain,
                            bases=[
                                node_text(c)
                                for c in superclass.named_children
                                if c.type != "comment"
                            ]
                            if superclass
                            else [],
                        )
                if node.type in {"class", "module"}:
                    nesting = (qualified, *nesting)
        uncertain = uncertain or node.type not in {"program", "body_statement", "class", "module"}
        for child in node.named_children:
            visit(child, nesting, uncertain)

    visit(tree)
    return bindings


def base_link(definition, expression, classes, bindings):
    result = {"expression": expression, "targets": [], "resolution": "unknown"}
    if not constant_path(expression) or "ruby_name" not in definition:
        return {**result, "evidence": "computed Ruby superclass expression; not resolved"}
    visible = [b for b in bindings if b["start"] < definition["ruby_start"]]
    names = lookup_names(expression, definition["ruby_nesting"])
    parts = expression.lstrip(":").split("::")
    prefixes = lookup_names(
        ("::" if expression.startswith("::") else "") + parts[0],
        definition["ruby_nesting"],
    )
    chosen = next(
        (
            (prefix, name)
            for prefix, name in zip(prefixes, names)
            if any(b["name"] == prefix for b in visible)
        ),
        None,
    )
    candidates = [s for s in classes if s["language"] == "ruby" and s["id"] != definition["id"]]
    if chosen:
        prefix, name = chosen
        if (
            not expression.startswith("::")
            and prefix == parts[0]
            and any(b["name"] in definition["ruby_nesting"] and b["ancestors"] for b in visible)
        ):
            return {
                **result,
                "evidence": "inherited Ruby constant lookup required before global fallback",
            }
        guards = [b for b in visible if name == b["name"] or name.startswith(b["name"] + "::")]
        if any(b["kind"] not in {"class", "module"} or b["uncertain"] for b in guards):
            return {**result, "evidence": "reassigned or conditional Ruby constant; not resolved"}
        local = [
            s
            for s in candidates
            if s.get("ruby_name") == name
            and s["path"] == definition["path"]
            and s.get("ruby_start", definition["ruby_start"]) < definition["ruby_start"]
        ]
        if not local:
            external = [
                s
                for s in candidates
                if s.get("ruby_name") == name and s["path"] != definition["path"]
            ]
            return {
                **result,
                "targets": [s["id"] for s in external],
                "resolution": "ambiguous" if external else "unknown",
                "evidence": "nearest Ruby namespace candidates; file loading not proven",
            }
        proven = (
            len(local) == 1 and not definition["ruby_uncertain"] and not local[0]["ruby_uncertain"]
        )
        return {
            **result,
            "targets": [s["id"] for s in local],
            "resolution": "resolved" if proven else "ambiguous" if local else "unknown",
            "evidence": "preceding Ruby class in nearest lexical constant namespace"
            if proven
            else "nearest Ruby constant namespace has no unique unconditional class",
        }
    candidates = [s for s in candidates if s.get("ruby_name") in names]
    return {
        **result,
        "targets": [s["id"] for s in candidates],
        "resolution": "ambiguous" if candidates else "unknown",
        "evidence": "Ruby constant candidates; file loading or declaration order not proven",
    }
