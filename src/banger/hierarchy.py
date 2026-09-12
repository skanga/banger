"""Class ancestry bindings with explicit unresolved candidates."""

import re

from banger.bindings import node_text, resolve_binding
from banger.cpp_hierarchy import base_link as cpp_base_link

CLASS_KINDS = {
    "class_definition",
    "class_declaration",
    "class_specifier",
    "class",
    "struct_item",
    "struct_specifier",
    "interface_declaration",
    "trait_item",
    "type_spec",
}


def declared_bases(node):
    """Read complete Java/C#/JavaScript/TypeScript/C++ base expressions."""
    result = []
    wrappers = {
        "superclass",
        "super_interfaces",
        "type_list",
        "base_list",
        "class_heritage",
        "implements_clause",
        "extends_type_clause",
        "base_class_clause",
    }

    def collect(part):
        if part.type in {"access_specifier", "comment"}:
            return
        if part.type == "extends_clause":
            result.append(re.sub(r"^extends\s+", "", node_text(part)))
        elif part.type in wrappers:
            for child in part.named_children:
                collect(child)
        else:
            result.append(node_text(part))

    for child in node.named_children:
        if child.type in wrappers:
            collect(child)
    return result


def csharp_namespace(node):
    names = []
    parent = node.parent
    while parent:
        if parent.type == "namespace_declaration":
            names.append(node_text(parent.child_by_field_name("name")))
        if parent.type == "compilation_unit":
            names.extend(
                node_text(child.child_by_field_name("name"))
                for child in parent.named_children
                if child.type == "file_scoped_namespace_declaration"
            )
        parent = parent.parent
    return ".".join(reversed(names))


def base_links(index, definition):
    if not definition["bases"]:
        return []
    classes = [s for s in index.symbols.values() if s["kind"] in CLASS_KINDS]
    result = []
    for expression in definition["bases"]:
        if definition["language"] == "cpp":
            result.append(
                cpp_base_link(
                    definition,
                    expression,
                    classes,
                    index.files[definition["path"]].get("cpp_type_bindings", []),
                )
            )
            continue
        candidates = []
        proven = False
        evidence = "name candidates only; language-specific binding not proven"
        if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", expression):
            result.append(
                {
                    "expression": expression,
                    "targets": [],
                    "resolution": "unknown",
                    "evidence": "dynamic or parameterized base expression",
                }
            )
            continue
        parts = expression.split(".")
        candidates = [
            s for s in classes if s["name"] == parts[-1] and s["language"] == definition["language"]
        ]
        file = index.files[definition["path"]]
        if definition["language"] == "python":
            scopes = []
            parent = definition["parent"]
            while parent:
                scopes.append(parent)
                parent = index.symbols[parent]["parent"]
            scopes.append(None)
            imported = None
            lexical = []
            shadowed = False
            for scope in scopes:
                owner = index.symbols.get(scope, {})
                shadowed = parts[0] in owner.get("parameters", []) or any(
                    a["scope"] == scope and a["name"] == parts[0] and a["line"] < definition["line"]
                    for a in file.get("assignments", [])
                )
                if shadowed:
                    break
                lexical = [
                    s
                    for s in classes
                    if s["path"] == definition["path"]
                    and s["parent"] == scope
                    and s["name"] == parts[0]
                    and s["line"] < definition["line"]
                ]
                bindings = (
                    file.get("scoped_imports", {}).get(scope, {}) if scope else file["imports"]
                )
                imported = bindings.get(parts[0])
                if lexical or imported:
                    break
            if shadowed:
                evidence = "value binding shadows class; runtime base unknown"
            elif lexical and not imported:
                for member in parts[1:]:
                    parents = {s["id"] for s in lexical}
                    lexical = [s for s in classes if s["parent"] in parents and s["name"] == member]
                candidates = lexical
                proven = True
                evidence = "nearest lexical class declaration"
            elif imported:
                qualified = imported.split(".") + parts[1:]
                module = "/".join(qualified[:-1])
                paths = {
                    prefix + module + suffix
                    for prefix in ("", "src/")
                    for suffix in (".py", "/__init__.py")
                }
                candidates = [
                    s
                    for s in classes
                    if s["path"] in paths and s["name"] == qualified[-1] and s["parent"] is None
                ]
                proven = True
                evidence = "Python imported class declaration"
        elif definition["language"] in {"javascript", "typescript", "tsx"}:
            by_name = {}
            for symbol in classes:
                by_name.setdefault(symbol["name"], []).append(symbol)
            binding = resolve_binding(
                {"path": definition["path"], "name": expression}, index, by_name
            )
            if binding:
                class_ids = {s["id"] for s in classes}
                binding["targets"] = [t for t in binding["targets"] if t in class_ids]
                if not binding["targets"]:
                    binding["resolution"] = "unknown"
                result.append({"expression": expression, **binding})
                continue
            if len(parts) == 1:
                candidates = [
                    s
                    for s in candidates
                    if s["path"] == definition["path"]
                    and s["parent"] == definition["parent"]
                    and s["line"] <= definition["line"]
                    and s["id"] != definition["id"]
                ]
                proven = True
                evidence = "local class or interface declaration"
        elif definition["language"] in {"java", "csharp"}:
            binding = file.get("module_imports", {}).get(parts[0])
            namespaces = file.get("using_namespaces", []) + [definition.get("namespace", "")]
            if binding:
                qualified = binding["module"].split(".") + parts[1:]
                namespaces = [".".join(qualified[:-1])]
                candidates = [
                    s
                    for s in classes
                    if s["name"] == qualified[-1] and s["language"] == definition["language"]
                ]
            elif len(parts) > 1:
                namespaces = [".".join(parts[:-1])]
            candidates = [
                s
                for s in candidates
                if s["parent"] is None and s.get("namespace", "") in namespaces
            ]
            proven = True
            evidence = "declared package/namespace and imported type"
        result.append(
            {
                "expression": expression,
                "targets": [s["id"] for s in candidates],
                "resolution": "resolved"
                if proven and len(candidates) == 1
                else "ambiguous"
                if candidates
                else "unknown",
                "evidence": evidence,
            }
        )
    return result
