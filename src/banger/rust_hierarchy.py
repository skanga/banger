"""Declared Rust supertraits with same-file module and explicit-use evidence."""

import re
from pathlib import PurePosixPath

from banger.bindings import node_text


def declaration_scope(node):
    scope = []
    conditional = False
    current = node
    while current:
        previous = current.prev_named_sibling
        while previous and previous.type in {"attribute_item", "line_comment", "block_comment"}:
            conditional |= previous.type == "attribute_item"
            previous = previous.prev_named_sibling
        current = current.parent
        if current and current.type == "mod_item":
            scope.append(node_text(current.child_by_field_name("name")))
        elif current and current.type == "block":
            scope.append(f"@{current.start_byte}")
    return {"rust_scope": list(reversed(scope)), "rust_conditional": conditional}


def nominal_name(node):
    if node is None or node.has_error:
        return None
    if node.type == "generic_type":
        return nominal_name(node.child_by_field_name("type"))
    value = node_text(node)
    return value if re.fullmatch(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", value) else None


def trait_metadata(node):
    parameters = node.child_by_field_name("type_parameters")
    bounds = [node.child_by_field_name("bounds")]
    for child in node.named_children:
        if child.type == "where_clause":
            bounds.extend(
                predicate.child_by_field_name("bounds")
                for predicate in child.named_children
                if node_text(predicate.child_by_field_name("left")) == "Self"
            )
    parts = [
        part
        for group in bounds
        if group
        for part in group.named_children
        if part.type not in {"lifetime", "line_comment", "block_comment"}
    ]
    return {
        **declaration_scope(node),
        "bases": [node_text(part) for part in parts],
        "rust_base_names": {node_text(part): nominal_name(part) for part in parts},
        "rust_type_parameters": [
            node_text(c.child_by_field_name("name"))
            for c in parameters.named_children
            if c.type == "type_parameter"
        ]
        if parameters
        else [],
    }


def use_bindings(tree):
    result = []
    stack = [tree]
    while stack:
        node = stack.pop()
        stack.extend(reversed(node.named_children))
        if node.type not in {"use_declaration", "type_item"}:
            continue
        scope = declaration_scope(node)
        if node.type == "type_item":
            result.append(
                {**scope, "alias": node_text(node.child_by_field_name("name")), "path": None}
            )
            continue
        argument = node.child_by_field_name("argument")
        alias = node_text(argument.child_by_field_name("alias")) if argument else ""
        path = nominal_name(argument.child_by_field_name("path") if alias else argument)
        result.append(
            {**scope, "alias": alias or path.split("::")[-1] if path else "*", "path": path}
        )
    return result


def qualified_scope(name, scope, path):
    parts = name.split("::")
    modules = [part for part in scope if not part.startswith("@")]
    if parts[0] == "crate":
        if PurePosixPath(path).as_posix() not in {"lib.rs", "main.rs", "src/lib.rs", "src/main.rs"}:
            return None
        modules = []
        parts.pop(0)
    elif parts[0] == "self":
        parts.pop(0)
    elif parts[0] == "super":
        while parts and parts[0] == "super":
            if not modules:
                return None
            modules.pop()
            parts.pop(0)
    else:
        modules = list(scope)
    return [*modules, *parts[:-1]], parts[-1]


def base_link(index, definition, expression):
    result = {"expression": expression, "targets": [], "resolution": "unknown"}
    name = definition.get("rust_base_names", {}).get(expression)
    if not name:
        return {**result, "evidence": "unsupported Rust trait bound; not resolved"}
    if name.split("::")[0] in definition.get("rust_type_parameters", []):
        return {**result, "evidence": "Rust type parameter shadows trait name"}
    scope = definition["rust_scope"]
    bindings = index.files[definition["path"]].get("rust_use_bindings", [])
    traits = [
        s
        for s in index.symbols.values()
        if s["kind"] == "trait_item" and s["path"] == definition["path"]
    ]
    scopes = [scope]
    while scopes[-1] and scopes[-1][-1].startswith("@"):
        scopes.append(scopes[-1][:-1])
    for lookup in scopes:
        imports = [
            b
            for b in bindings
            if b["rust_scope"] == lookup and b["alias"] in {name.split("::")[0], "*"}
        ]
        explicit = [b for b in imports if b["alias"] != "*"]
        resolved_name = name
        if explicit:
            if len(explicit) != 1 or not explicit[0]["path"] or explicit[0]["rust_conditional"]:
                return {**result, "evidence": "ambiguous or attributed Rust use/type binding"}
            resolved_name = explicit[0]["path"] + name[len(explicit[0]["alias"]) :]
        target = qualified_scope(resolved_name, lookup, definition["path"])
        if target is None:
            return {
                **result,
                "evidence": "Rust crate or parent-module path needs external module mapping",
            }
        target_scope, target_name = target
        candidates = [
            s for s in traits if s.get("rust_scope") == target_scope and s["name"] == target_name
        ]
        if candidates:
            local_collision = explicit and any(
                s.get("rust_scope") == lookup and s["name"] == name for s in traits
            )
            proven = (
                len(candidates) == 1
                and not definition["rust_conditional"]
                and not candidates[0]["rust_conditional"]
                and not local_collision
            )
            return {
                **result,
                "targets": [s["id"] for s in candidates],
                "resolution": "resolved" if proven else "ambiguous",
                "evidence": "same-file Rust trait in declared module scope or explicit use"
                if proven
                else "duplicate, attributed or conflicting Rust trait declaration",
            }
        if imports or "::" in name:
            break
    external = []
    for symbol in index.symbols.values():
        if (
            symbol["kind"] != "trait_item"
            or symbol["path"] == definition["path"]
            or symbol["name"] != target_name
        ):
            continue
        file = PurePosixPath(symbol["path"])
        modules = list(file.with_suffix("").parts)
        if modules and modules[0] == "src":
            modules.pop(0)
        if modules and modules[-1] in {"lib", "main", "mod"}:
            modules.pop()
        if modules + symbol.get("rust_scope", []) == target_scope:
            external.append(symbol["id"])
    return {
        **result,
        "targets": external,
        "resolution": "ambiguous" if external else "unknown",
        "evidence": "Rust trait not found in visible same-file scope; external modules, glob imports and re-exports unproven",
    }
