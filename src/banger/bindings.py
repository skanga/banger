"""Language-specific import bindings; unsupported forms remain unresolved."""

import re
from pathlib import Path


def node_text(node):
    return node.text.decode("utf-8", errors="replace") if node else ""


def extract_bindings(language, tree):
    imports, namespaces = {}, []
    namespace = ""
    stack = [tree]
    while stack:
        node = stack.pop()
        stack.extend(reversed(node.named_children))
        if language in {"javascript", "typescript", "tsx"} and node.type == "import_statement":
            source = node_text(node.child_by_field_name("source")).strip("\"'")
            for clause in node.named_children:
                if clause.type != "import_clause":
                    continue
                for child in clause.named_children:
                    if child.type == "identifier":
                        imports[node_text(child)] = {"module": source, "member": "default"}
                    elif child.type == "namespace_import":
                        imports[node_text(child.named_children[-1])] = {
                            "module": source,
                            "member": "*",
                        }
                    elif child.type == "named_imports":
                        for spec in child.named_children:
                            name = node_text(spec.child_by_field_name("name"))
                            alias = node_text(spec.child_by_field_name("alias")) or name
                            imports[alias] = {"module": source, "member": name}
        elif language == "go" and node.type == "import_spec":
            module = node_text(node.child_by_field_name("path")).strip('"`')
            alias = node_text(node.child_by_field_name("name")) or module.rsplit("/", 1)[-1]
            imports[alias] = {"module": module, "member": "*"}
        elif language == "rust" and node.type == "use_declaration":
            argument = node.child_by_field_name("argument")
            alias = node_text(argument.child_by_field_name("alias")) if argument else ""
            value = (
                node_text(argument.child_by_field_name("path")) if alias else node_text(argument)
            )
            if value and "{" not in value and "*" not in value:
                parts = value.split("::")
                imports[alias or parts[-1]] = {"module": "::".join(parts[:-1]), "member": parts[-1]}
        elif language == "java" and node.type == "import_declaration":
            value = re.sub(r"^import\s+(?:static\s+)?|;\s*$", "", node_text(node)).strip()
            imports[value.rsplit(".", 1)[-1]] = {"module": value, "member": "*"}
        elif language == "java" and node.type == "package_declaration":
            namespace = re.sub(r"^package\s+|;\s*$", "", node_text(node)).strip()
        elif language == "csharp" and node.type == "using_directive":
            namespaces.append(re.sub(r"^using\s+|;\s*$", "", node_text(node)).strip())
        elif language == "csharp" and node.type in {
            "namespace_declaration",
            "file_scoped_namespace_declaration",
        }:
            namespace = node_text(node.child_by_field_name("name"))
    return {"module_imports": imports, "using_namespaces": namespaces, "namespace": namespace}


def resolve_binding(call, index, by_name):
    file = index.files[call["path"]]
    language = file.get("language")
    parts = re.split(r"\.|::|->", call["name"])
    binding = file.get("module_imports", {}).get(parts[0])
    candidates, evidence, external = [], "", False
    if language in {"javascript", "typescript", "tsx"} and binding:
        module = binding["module"]
        member = parts[-1] if binding["member"] == "*" else binding["member"]
        if not module.startswith("."):
            return {
                "targets": [],
                "resolution": "unknown",
                "evidence": "bare module import may be a package or project path alias; not resolved",
            }
        target = (index.root / call["path"]).parent / module
        target = target.resolve()
        files = set()
        for suffix in ("", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js"):
            candidate = Path(str(target) + suffix)
            if candidate.is_relative_to(index.root):
                files.add(candidate.relative_to(index.root).as_posix())
        if member == "default":
            candidates = [
                s for s in index.symbols.values() if s["path"] in files and s.get("default_export")
            ]
        else:
            candidates = [
                s for s in by_name.get(member, []) if s["path"] in files and s["parent"] is None
            ]
        evidence = "relative module import binding"
    elif language == "go" and binding:
        module = binding["module"]
        module_name = index.go_module
        if module_name and (module == module_name or module.startswith(module_name + "/")):
            directory = module[len(module_name) :].strip("/") or "."
            candidates = [
                s
                for s in by_name.get(parts[-1], [])
                if Path(s["path"]).parent.as_posix() == directory and s["parent"] is None
            ]
        else:
            external = True
        evidence = "Go module import path"
    elif language == "rust" and binding:
        module_parts = binding["module"].split("::")
        directory = (index.root / "src") if (index.root / "src").is_dir() else index.root
        if module_parts[0] == "crate":
            module_parts = module_parts[1:]
        elif module_parts[0] in {"self", "super"}:
            directory = (index.root / call["path"]).parent
            if module_parts[0] == "super":
                directory = directory.parent
            module_parts = module_parts[1:]
        target = directory.joinpath(*module_parts)
        files = {Path(str(target) + ".rs"), target / "mod.rs"}
        candidates = [
            s
            for s in by_name.get(binding["member"], [])
            if index.root / s["path"] in files and s["parent"] is None
        ]
        evidence = "Rust explicit use binding"
    elif language in {"java", "csharp"} and len(parts) >= 2:
        classname = parts[-2]
        namespaces = file.get("using_namespaces", []) + [file.get("namespace", "")]
        if binding:
            qualified = binding["module"].split(".")
            classname = qualified[-1]
            namespaces = [".".join(qualified[:-1])]
        for symbol in by_name.get(parts[-1], []):
            parent = index.symbols.get(symbol["parent"], {})
            if (
                parent.get("name") == classname
                and "static" in symbol["signature"].split()
                and index.files[symbol["path"]].get("namespace", "") in namespaces
            ):
                candidates.append(symbol)
        if not candidates and not binding:
            return None
        evidence = "Imported class and static member declaration"
    elif language == "go" and len(parts) == 1:
        candidates = [
            s
            for s in by_name.get(parts[0], [])
            if s["language"] == "go"
            and Path(s["path"]).parent == Path(call["path"]).parent
            and s["parent"] is None
        ]
        if not candidates:
            return None
        evidence = "Go package-level declaration"
    else:
        return None
    return {
        "targets": [s["id"] for s in candidates],
        "evidence": evidence,
        "resolution": "resolved"
        if len(candidates) == 1
        else "ambiguous"
        if candidates
        else "external"
        if external
        else "unknown",
    }
