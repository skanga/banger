"""Declared Go embedding; method promotion and interface satisfaction are separate."""

from pathlib import PurePosixPath

from banger.bindings import node_text


def file_metadata(tree, path):
    package = next((c for c in tree.named_children if c.type == "package_clause"), None)
    imports = []
    stack = [tree]
    while stack:
        node = stack.pop()
        stack.extend(reversed(node.named_children))
        if node.type == "import_spec":
            imports.append(
                {
                    "alias": node_text(node.child_by_field_name("name")),
                    "module": node_text(node.child_by_field_name("path")).strip('"`'),
                }
            )
    # Build selection is not evaluated by this source index.
    conditional = (
        any(
            c.type == "comment" and node_text(c).startswith(("//go:build", "// +build"))
            for c in tree.named_children
        )
        or "_" in PurePosixPath(path).stem
    )
    return {
        "go_package": node_text(package.named_children[0]) if package else "",
        "go_imports": imports,
        "go_conditional": conditional,
    }


def nominal_name(node):
    if node is None or node.has_error:
        return None
    if node.type in {"type_identifier", "qualified_type"}:
        return node_text(node)
    if node.type == "generic_type":
        return nominal_name(node.child_by_field_name("type"))
    if node.type == "type_elem" and len(node.named_children) == 1:
        return nominal_name(node.named_children[0])
    return None


def type_metadata(node):
    body = node.child_by_field_name("type")
    expressions = {}
    if body and body.type == "struct_type":
        fields = next((c for c in body.named_children if c.type == "field_declaration_list"), None)
        for field in fields.named_children if fields else []:
            if field.type != "field_declaration" or field.child_by_field_name("name"):
                continue
            kind = field.child_by_field_name("type")
            if kind:
                expression = field.text[: kind.end_byte - field.start_byte].decode("utf-8")
                expressions[expression] = nominal_name(kind)
    elif body and body.type == "interface_type":
        expressions = {
            node_text(c): nominal_name(c) for c in body.named_children if c.type == "type_elem"
        }
    parameters = node.child_by_field_name("type_parameters")
    return {
        "bases": list(expressions),
        "go_base_names": expressions,
        "go_type_parameters": [
            node_text(name)
            for param in parameters.named_children
            if parameters
            for name in param.children_by_field_name("name")
        ]
        if parameters
        else [],
    }


def base_link(index, definition, expression):
    result = {
        "expression": expression,
        "relationship": "embedding",
        "targets": [],
        "resolution": "unknown",
        "evidence": "nominal embedding target not proven; no method-set inference",
    }
    name = definition.get("go_base_names", {}).get(expression)
    if not name or definition["parent"] is not None:
        return result
    parts = name.split(".")
    if parts[0] in definition.get("go_type_parameters", []):
        return result
    file = index.files[definition["path"]]
    directory = PurePosixPath(definition["path"]).parent
    package = file["go_package"]
    if len(parts) == 2:
        matches = []
        for imported in file["go_imports"]:
            module = imported["module"]
            if not index.go_module or not (
                module == index.go_module or module.startswith(index.go_module + "/")
            ):
                continue
            target_dir = PurePosixPath(module[len(index.go_module) :].strip("/") or ".")
            packages = {
                f["go_package"]
                for path, f in index.files.items()
                if f.get("language") == "go" and PurePosixPath(path).parent == target_dir
            }
            alias = imported["alias"]
            if alias == parts[0] or not alias and parts[0] in packages:
                matches.append((target_dir, packages))
        if len(matches) != 1 or not parts[-1][0].isupper():
            return result
        directory, packages = matches[0]
        if len(packages) != 1:
            return result
        package = next(iter(packages))
    elif len(parts) != 1 or any(i["alias"] in {".", name} for i in file["go_imports"]):
        return result
    candidates = [
        s
        for s in index.symbols.values()
        if s["language"] == "go"
        and s["kind"] == "type_spec"
        and s["parent"] is None
        and s["name"] == parts[-1]
        and PurePosixPath(s["path"]).parent == directory
        and index.files[s["path"]].get("go_package") == package
    ]
    result["targets"] = [s["id"] for s in candidates]
    uncertain = file["go_conditional"] or any(
        index.files[s["path"]]["go_conditional"] for s in candidates
    )
    result["resolution"] = (
        "resolved"
        if len(candidates) == 1 and not uncertain
        else "ambiguous"
        if candidates
        else "unknown"
    )
    result["evidence"] = (
        "declared embedding with package/module path; build selection unproven"
        if uncertain
        else "declared embedding with matching package and module path"
    )
    return result
