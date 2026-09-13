"""Structured source index with explicit static resolution evidence."""

import ast
import hashlib
import inspect
import re
from collections import Counter, deque
from itertools import pairwise
from pathlib import Path

from tree_sitter_language_pack import get_parser

from banger.bindings import extract_bindings, resolve_binding
from banger.cpp_hierarchy import declaration_scope as cpp_declaration_scope
from banger.cpp_hierarchy import type_bindings as cpp_type_bindings
from banger.discovery import discover_files
from banger.gates import binding_regressions, call_key
from banger.hierarchy import base_links, csharp_namespace, declared_bases
from banger.outline import source_outline
from banger.python_scopes import annotate_value_scopes
from banger.receivers import ReceiverBindings

LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".h": "c",
    ".c": "c",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
}
DEFINITIONS = {
    "function_definition",
    "function_declaration",
    "function_item",
    "method_definition",
    "method_declaration",
    "method",
    "singleton_method",
    "constructor_declaration",
    "class_definition",
    "class_declaration",
    "class_specifier",
    "class",
    "struct_item",
    "struct_specifier",
    "interface_declaration",
    "trait_item",
    "enum_item",
    "type_spec",
}
CALLS = {
    "call",
    "call_expression",
    "method_invocation",
    "invocation_expression",
    "object_creation_expression",
    "new_expression",
}


def text(node) -> str:
    return node.text.decode("utf-8", errors="replace") if node else ""


def walk(node):
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def declaration_comments(node, data):
    """Return adjacent leading comments, preserving their source formatting."""
    while node.parent and node.parent.type in {
        "export_statement",
        "lexical_declaration",
        "variable_declaration",
        "decorated_definition",
    }:
        node = node.parent
    comments = []
    following = node
    previous = node.prev_named_sibling
    while previous and previous.type in {"comment", "line_comment", "block_comment"}:
        gap = data[previous.end_byte : following.start_byte]
        line_start = data.rfind(b"\n", 0, previous.start_byte) + 1
        end_row = previous.end_point.row - int(previous.text.endswith(b"\n"))
        if (
            gap.strip()
            or following.start_point.row - end_row != 1
            or data[line_start : previous.start_byte].strip()
        ):
            break
        comments.append(text(previous).rstrip())
        following, previous = previous, previous.prev_named_sibling
    return "\n".join(reversed(comments))


class CodeIndex:
    def __init__(self, root: Path, state=None):
        self.root = root.resolve()
        self.state = state
        self.files = (state.artifact("index", "files-v17") or {}) if state else {}
        self.go_module = ""
        self.symbols: dict[str, dict] = {}
        self.calls: list[dict] = []
        self.hierarchies: dict[str, dict] = {}

    def syntax_errors(self, path: str, source: bytes) -> list[dict]:
        language = LANGUAGES.get(Path(path).suffix.lower())
        if not language:
            return []
        tree = get_parser(language).parse(source)
        return [
            {"line": n.start_point.row + 1, "kind": n.type}
            for n in walk(tree.root_node)
            if n.type == "ERROR" or n.is_missing
        ]

    def refresh(self) -> dict:
        go_mod = self.root / "go.mod"
        if go_mod.is_file():
            match = re.search(r"^module\s+(\S+)", go_mod.read_text(encoding="utf-8"), re.MULTILINE)
            self.go_module = match.group(1).strip('"') if match else ""
        found = set()
        changed = 0
        for path in discover_files(self.root):
            if path.suffix.lower() not in LANGUAGES:
                continue
            relative = path.relative_to(self.root).as_posix()
            found.add(relative)
            try:
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if self.files.get(relative, {}).get("digest") != digest:
                    self.files[relative] = self._parse(relative, data, digest)
                    changed += 1
            except OSError as exc:
                self.files[relative] = {
                    "symbols": [],
                    "calls": [],
                    "imports": {},
                    "error": str(exc),
                }
        self.files = {p: f for p, f in self.files.items() if p in found}
        self.symbols = {s["id"]: s for f in self.files.values() for s in f["symbols"]}
        self.calls = [dict(c) for f in self.files.values() for c in f["calls"]]
        self._build_hierarchies()
        self._resolve_calls()
        if self.state:
            self.state.put_artifact("index", "files-v17", self.files)
        return {
            "files": len(self.files),
            "symbols": len(self.symbols),
            "changed": changed,
            "errors": {p: f["error"] for p, f in self.files.items() if f.get("error")},
        }

    def _parse(self, path: str, data: bytes, digest: str) -> dict:
        language = LANGUAGES[Path(path).suffix.lower()]
        tree = get_parser(language).parse(data)
        module_bindings = extract_bindings(language, tree.root_node)
        if language == "cpp":
            module_bindings["cpp_type_bindings"] = cpp_type_bindings(tree.root_node)
        symbols, calls, references, assignments, returns = [], [], [], [], []
        outlines = {}

        def visit(node, scope=None):
            value = node.child_by_field_name("value")
            assigned_function = (
                node.type == "variable_declarator"
                and value
                and value.type in {"arrow_function", "function_expression"}
            )
            if node.type in DEFINITIONS or assigned_function:
                name_node = node.child_by_field_name("name")
                declarator = node.child_by_field_name("declarator")
                while not name_node and declarator:
                    if declarator.type in {
                        "identifier",
                        "field_identifier",
                        "qualified_identifier",
                    }:
                        name_node = declarator
                        break
                    declarator = declarator.child_by_field_name("declarator")
                if name_node:
                    name = text(name_node)
                    body = (value if assigned_function else node).child_by_field_name("body")
                    identity = f"{path}:{node.start_point.row + 1}:{name}"
                    bases = node.child_by_field_name("superclasses") or node.child_by_field_name(
                        "superclass"
                    )
                    if not bases:
                        bases = next(
                            (
                                n
                                for n in node.named_children
                                if n.type in {"base_list", "base_class_clause", "class_heritage"}
                            ),
                            None,
                        )
                    parameters = node.child_by_field_name("parameters")
                    if not parameters:
                        parameters = next(
                            (
                                n
                                for n in walk(node)
                                if n.type
                                in {
                                    "parameter_list",
                                    "parameters",
                                    "formal_parameters",
                                    "method_parameters",
                                }
                            ),
                            None,
                        )
                    parameter_names = []
                    for param in parameters.named_children if parameters else []:
                        parameter = (
                            param.child_by_field_name("name")
                            or param.child_by_field_name("pattern")
                            or param.child_by_field_name("declarator")
                        )
                        if not parameter and param.type == "identifier":
                            parameter = param
                        if parameter:
                            parameter_names.append(text(parameter))
                    outlines[identity] = source_outline(
                        node,
                        body,
                        data,
                        expression_body=bool(
                            assigned_function and body and body.type != "statement_block"
                        ),
                    )
                    symbols.append(
                        {
                            "id": identity,
                            "name": name,
                            "path": path,
                            "language": language,
                            "namespace": csharp_namespace(node)
                            if language == "csharp"
                            else module_bindings["namespace"],
                            "kind": node.type,
                            "line": node.start_point.row + 1,
                            "end_line": node.end_point.row + 1,
                            "parent": scope,
                            "signature": data[
                                node.start_byte : body.start_byte if body else node.end_byte
                            ]
                            .decode("utf-8", errors="replace")
                            .strip(),
                            "bases": declared_bases(node)
                            if language
                            in {"java", "csharp", "javascript", "typescript", "tsx", "cpp"}
                            else re.findall(r"[A-Za-z_]\w*", text(bases)),
                            **(cpp_declaration_scope(node) if language == "cpp" else {}),
                            "parameters": parameter_names,
                            "bindings": [],
                            "documentation": declaration_comments(node, data),
                            "default_export": bool(
                                node.parent
                                and node.parent.type == "export_statement"
                                and text(node.parent).startswith("export default")
                            ),
                        }
                    )
                    scope = identity
                    if body and (
                        language in {"rust", "ruby"}
                        or assigned_function
                        and body.type != "statement_block"
                    ):
                        last = (
                            body.named_children[-1]
                            if body.named_children and body.type in {"block", "body_statement"}
                            else body
                        )
                        returns.append(
                            {
                                "scope": scope,
                                "expression": text(last),
                                "line": last.start_point.row + 1,
                                "path": path,
                            }
                        )
            if node.type == "return_statement" and node.named_children:
                returns.append(
                    {
                        "scope": scope,
                        "expression": text(node.named_children[0]),
                        "line": node.start_point.row + 1,
                        "path": path,
                    }
                )
            if node.type in {"identifier", "field_identifier", "property_identifier"}:
                references.append(
                    {
                        "name": text(node),
                        "scope": scope,
                        "path": path,
                        "line": node.start_point.row + 1,
                        "context": node.parent.type if node.parent else "root",
                    }
                )
            if not assigned_function and node.type in {
                "assignment",
                "assignment_expression",
                "variable_declarator",
                "init_declarator",
                "short_var_declaration",
                "let_declaration",
            }:
                left = (
                    node.child_by_field_name("left")
                    or node.child_by_field_name("name")
                    or node.child_by_field_name("pattern")
                    or node.child_by_field_name("declarator")
                )
                right = node.child_by_field_name("right") or node.child_by_field_name("value")
                if left and right:
                    assignments.append(
                        {
                            "name": text(left),
                            "expression": text(right),
                            "scope": scope,
                            "line": node.start_point.row + 1,
                            "path": path,
                        }
                    )
                    owner = next((s for s in symbols if s["id"] == scope), None)
                    if owner:
                        owner["bindings"].append(text(left))
            if node.type in CALLS:
                target = (
                    node.child_by_field_name("function")
                    or node.child_by_field_name("name")
                    or node.child_by_field_name("method")
                    or node.child_by_field_name("type")
                    or node.child_by_field_name("constructor")
                )
                receiver = node.child_by_field_name("object") or node.child_by_field_name(
                    "receiver"
                )
                name = (text(receiver) + "." if receiver else "") + text(target)
                if name:
                    arguments = node.child_by_field_name("arguments")
                    holder = None
                    parent = node.parent
                    while parent and parent.type not in DEFINITIONS:
                        if parent.type == "arrow_function":
                            holder = "$return"
                            break
                        if parent.type in {
                            "assignment",
                            "assignment_expression",
                            "variable_declarator",
                            "init_declarator",
                            "short_var_declaration",
                            "let_declaration",
                        }:
                            holder = text(
                                parent.child_by_field_name("left")
                                or parent.child_by_field_name("name")
                                or parent.child_by_field_name("pattern")
                                or parent.child_by_field_name("declarator")
                            )
                            break
                        if parent.type == "return_statement":
                            holder = "$return"
                            break
                        parent = parent.parent
                    calls.append(
                        {
                            "name": name,
                            "caller": scope,
                            "path": path,
                            "line": node.start_point.row + 1,
                            "arguments": [text(n) for n in arguments.named_children]
                            if arguments
                            else [],
                            "expression": text(node),
                            "holder": holder,
                        }
                    )
            for child in node.named_children:
                visit(child, scope)

        visit(tree.root_node)
        imports = {}
        scoped_imports = {}
        value_imports = []
        module_value_imports = []
        if language == "python":
            annotate_value_scopes(data, path, symbols)
            try:
                for node in ast.walk(ast.parse(data)):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        declaration = next(
                            (
                                s
                                for s in symbols
                                if s["line"] == node.lineno and s["name"] == node.name
                            ),
                            None,
                        )
                        if declaration:
                            if isinstance(node, ast.ClassDef):
                                declaration["bases"] = [ast.unparse(base) for base in node.bases]
                            declaration["documentation"] = (
                                ast.get_docstring(node) or declaration["documentation"]
                            )
                    if (
                        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and not node.decorator_list
                    ):
                        owner = next(
                            (
                                s
                                for s in symbols
                                if s["line"] == node.lineno and s["name"] == node.name
                            ),
                            None,
                        )
                        if owner:
                            positional = node.args.posonlyargs + node.args.args
                            parent = next((s for s in symbols if s["id"] == owner["parent"]), {})
                            if positional and parent.get("kind") == "class_definition":
                                owner["implicit_receiver"] = positional[0].arg
                            required = len(positional) - len(node.args.defaults)
                            params = [
                                {
                                    "name": a.arg,
                                    "kind": "POSITIONAL_ONLY"
                                    if i < len(node.args.posonlyargs)
                                    else "POSITIONAL_OR_KEYWORD",
                                    "required": i < required,
                                }
                                for i, a in enumerate(positional)
                            ]
                            if node.args.vararg:
                                params.append(
                                    {
                                        "name": node.args.vararg.arg,
                                        "kind": "VAR_POSITIONAL",
                                        "required": True,
                                    }
                                )
                            params.extend(
                                {"name": a.arg, "kind": "KEYWORD_ONLY", "required": default is None}
                                for a, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
                            )
                            if node.args.kwarg:
                                params.append(
                                    {
                                        "name": node.args.kwarg.arg,
                                        "kind": "VAR_KEYWORD",
                                        "required": True,
                                    }
                                )
                            owner["signature_parameters"] = params
                            defaults = dict(
                                zip([a.arg for a in positional[required:]], node.args.defaults)
                            )
                            defaults.update(
                                (a.arg, default)
                                for a, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
                                if default is not None
                            )
                            owner["parameter_defaults"] = {
                                name: {
                                    "expression": ast.get_source_segment(
                                        data.decode("utf-8"), default
                                    )
                                    or ast.unparse(default),
                                    "path": path,
                                    "line": default.lineno,
                                    "scope": owner["parent"],
                                }
                                for name, default in defaults.items()
                            }
                    if isinstance(node, ast.Import):
                        enclosing = [
                            s for s in symbols if s["line"] <= node.lineno <= s["end_line"]
                        ]
                        owner = (
                            min(enclosing, key=lambda s: s["end_line"] - s["line"])
                            if enclosing
                            else None
                        )
                        bindings = scoped_imports.setdefault(owner["id"], {}) if owner else imports
                        for alias in node.names:
                            bindings[alias.asname or alias.name.split(".")[0]] = (
                                alias.name if alias.asname else alias.name.split(".")[0]
                            )
                            module_value_imports.append(
                                {
                                    "name": alias.asname or alias.name.split(".")[0],
                                    "access": alias.asname or alias.name,
                                    "module": alias.name,
                                    "scope": owner["id"] if owner else None,
                                    "path": path,
                                    "line": node.lineno,
                                }
                            )
                    elif isinstance(node, ast.ImportFrom):
                        enclosing = [
                            s for s in symbols if s["line"] <= node.lineno <= s["end_line"]
                        ]
                        owner = (
                            min(enclosing, key=lambda s: s["end_line"] - s["line"])
                            if enclosing
                            else None
                        )
                        bindings = scoped_imports.setdefault(owner["id"], {}) if owner else imports
                        module = node.module or ""
                        if node.level:
                            parent = Path(path).parent.parts
                            prefix = parent[: len(parent) - node.level + 1]
                            module = ".".join((*prefix, module)).strip(".")
                        for alias in node.names:
                            bindings[alias.asname or alias.name] = module + "." + alias.name
                            if alias.name != "*" and module:
                                value_imports.append(
                                    {
                                        "name": alias.asname or alias.name,
                                        "module": module,
                                        "member": alias.name,
                                        "scope": owner["id"] if owner else None,
                                        "path": path,
                                        "line": node.lineno,
                                    }
                                )
            except (SyntaxError, ValueError):
                pass
        return {
            **module_bindings,
            "language": language,
            "digest": digest,
            "symbols": symbols,
            "calls": calls,
            "imports": imports,
            "scoped_imports": scoped_imports,
            "value_imports": value_imports,
            "module_value_imports": module_value_imports,
            "references": references,
            "assignments": assignments,
            "returns": returns,
            "outlines": outlines,
            "error": "syntax errors" if tree.root_node.has_error else None,
        }

    def _resolve_calls(self):
        receivers = ReceiverBindings(self)
        by_name = {}
        for symbol in self.symbols.values():
            by_name.setdefault(symbol["name"], []).append(symbol)
        for call in self.calls:
            name = call["name"]
            leaf = re.split(r"\.|::|->", name)[-1]
            candidates = by_name.get(leaf, [])
            imported = self.files[call["path"]]["imports"].get(name.split(".")[0])
            visible = self._visible_scopes(call)
            for scope in reversed(visible):
                scoped = self.files[call["path"]].get("scoped_imports", {}).get(scope, {})
                imported = scoped.get(name.split(".")[0], imported)
            owner = self.symbols.get(call["caller"], {})
            receiver_binding = receivers.resolve(call, candidates)
            if receiver_binding:
                call.update(receiver_binding)
                continue
            shadowed = name.split(".")[0] in owner.get("parameters", []) + owner.get("bindings", [])
            if shadowed:
                call.update(
                    targets=[s["id"] for s in candidates],
                    resolution="ambiguous" if candidates else "unknown",
                    evidence="local value shadows declaration/import; runtime binding unknown",
                )
                continue
            language_binding = resolve_binding(call, self, by_name)
            if language_binding:
                call.update(language_binding)
                continue
            proven = False
            if imported:
                qualified = imported + ("." + name.split(".", 1)[1] if "." in name else "")
                parts = qualified.split(".")
                module = "/".join(parts[:-1])
                module_files = {
                    prefix + module + suffix
                    for prefix in ("", "src/")
                    for suffix in (".py", "/__init__.py")
                }
                candidates = [
                    s
                    for s in by_name.get(parts[-1], [])
                    if s["path"] in module_files and s["parent"] is None
                ]
                proven = len(candidates) == 1
                if not candidates:
                    package = imported.split(".")[0]
                    in_repo = any(
                        p == prefix + package + ".py" or p.startswith(prefix + package + "/")
                        for p in self.files
                        for prefix in ("", "src/")
                    )
                    call.update(
                        targets=[],
                        resolution="unknown" if in_repo else "external",
                        evidence="import binding",
                    )
                    continue
            elif not re.search(r"\.|::|->", name):
                local = [
                    s for s in candidates if s["path"] == call["path"] and s["parent"] in visible
                ]
                if local:
                    candidates = local
                    proven = len(local) == 1
            call.update(
                targets=[s["id"] for s in candidates],
                resolution="resolved" if proven else "ambiguous" if candidates else "unknown",
                evidence="import binding"
                if imported
                else "lexical declaration"
                if proven
                else "name candidates only; receiver/type binding not proven",
            )

    def _visible_scopes(self, call):
        visible = [call["caller"]]
        current = self.symbols.get(call["caller"], {})
        while current.get("parent"):
            parent = self.symbols[current["parent"]]
            if not (parent["language"] == "python" and parent["kind"] == "class_definition"):
                visible.append(parent["id"])
            current = parent
        visible.append(None)
        return visible

    def search_symbols(self, query: str) -> list[dict]:
        return [s for s in self.symbols.values() if query.casefold() in s["name"].casefold()]

    def preview_change(self, path: Path, after: bytes | None) -> dict:
        """Check known call bindings against a prospective file change without writing it."""
        if not path.is_relative_to(self.root):
            return {"regressions": [], "scope": "Outside indexed workspace"}
        return self.preview_changes({path: after})

    def preview_changes(self, changes: dict[Path, bytes | None]) -> dict:
        candidate = CodeIndex(self.root)
        candidate.go_module = self.go_module
        candidate.files = dict(self.files)
        outside = []
        for path, after in changes.items():
            if not path.is_relative_to(self.root):
                outside.append(str(path))
                continue
            relative = path.relative_to(self.root).as_posix()
            if after is None:
                candidate.files.pop(relative, None)
            elif path.suffix.lower() in LANGUAGES:
                candidate.files[relative] = self._parse(
                    relative, after, hashlib.sha256(after).hexdigest()
                )
        candidate.symbols = {s["id"]: s for f in candidate.files.values() for s in f["symbols"]}
        candidate.calls = [dict(c) for f in candidate.files.values() for c in f["calls"]]
        candidate._build_hierarchies()
        candidate._resolve_calls()

        regressions = binding_regressions(self, candidate)
        previous_errors = Counter(call_key(c, self) for c in self.calls if self._arity_error(c))
        for call in candidate.calls:
            error = candidate._arity_error(call)
            if error:
                key = call_key(call, candidate)
                if previous_errors[key]:
                    previous_errors[key] -= 1
                else:
                    regressions.append({**call, "signature_error": error})
        return {
            "regressions": regressions,
            "unindexed_paths": outside,
            "scope": "Known bindings and Python call signatures; not a full language type checker",
        }

    def _arity_error(self, call):
        if call["resolution"] != "resolved" or len(call["targets"]) != 1:
            return None
        definition = self.symbols[call["targets"][0]]
        if "signature_parameters" not in definition:
            return None
        try:
            expression = ast.parse(call["expression"], mode="eval").body
        except SyntaxError:
            return None
        if (
            not isinstance(expression, ast.Call)
            or any(isinstance(a, ast.Starred) for a in expression.args)
            or any(k.arg is None for k in expression.keywords)
        ):
            return None
        signature = inspect.Signature(
            [
                inspect.Parameter(
                    p["name"],
                    getattr(inspect.Parameter, p["kind"]),
                    default=inspect.Parameter.empty if p["required"] else None,
                )
                for p in definition["signature_parameters"]
            ]
        )
        try:
            signature.bind(
                *[None] * len(expression.args), **{k.arg: None for k in expression.keywords}
            )
        except TypeError as exc:
            return str(exc)
        return None

    def get_definition(self, symbol: str) -> dict:
        if symbol in self.symbols:
            return self.symbols[symbol]
        matches = [s for s in self.symbols.values() if s["name"] == symbol]
        if len(matches) != 1:
            raise ValueError(f"Specify a symbol ID; {len(matches)} definitions match {symbol!r}")
        return matches[0]

    def get_callers(self, symbol: str) -> list[dict]:
        identity = self.get_definition(symbol)["id"]
        return [c for c in self.calls if identity in c["targets"]]

    def _resolved_adjacency(self, reverse=False):
        adjacency = {}
        for call in self.calls:
            if call["resolution"] == "resolved":
                for target in call["targets"]:
                    key = target if reverse else call["caller"]
                    adjacency.setdefault(key, []).append((call, target))
        return adjacency

    def call_tree(self, symbol: str, reverse: bool = False) -> dict:
        identity = self.get_definition(symbol)["id"]
        adjacency = self._resolved_adjacency(reverse)
        seen, queue, edges = {identity}, deque([identity]), []
        while queue:
            current = queue.popleft()
            for call, target in adjacency.get(current, []):
                source = call["caller"]
                edges.append({"source": source, "target": target, "line": call["line"]})
                following = source if reverse else target
                if following and following not in seen:
                    seen.add(following)
                    queue.append(following)
        return {"nodes": sorted(seen), "edges": edges, "includes": "resolved edges only"}

    def trace_path(self, source: str, target: str) -> list[str]:
        source, target = self.get_definition(source)["id"], self.get_definition(target)["id"]
        adjacency = self._resolved_adjacency()
        queue, previous = deque([source]), {source: None}
        while queue:
            current = queue.popleft()
            if current == target:
                path = []
                while current is not None:
                    path.append(current)
                    current = previous[current]
                return path[::-1]
            for _, following in adjacency.get(current, []):
                if following not in previous:
                    previous[following] = current
                    queue.append(following)
        return []

    def trace_path_details(self, source: str, target: str) -> dict:
        path = self.trace_path(source, target)
        calls_by_step = {step: [] for step in pairwise(path)}
        for call in self.calls:
            if call["resolution"] == "resolved":
                for callee in call["targets"]:
                    step = (call["caller"], callee)
                    if step in calls_by_step:
                        calls_by_step[step].append(call)
        steps = []
        for caller, callee in pairwise(path):
            sites = [
                {
                    "path": call["path"],
                    "line": call["line"],
                    "expression": call["expression"],
                    "arguments": call["arguments"],
                    "return_holder": call["holder"],
                    "resolution": call["resolution"],
                    "evidence": call["evidence"],
                }
                for call in calls_by_step[(caller, callee)]
            ]
            steps.append(
                {
                    "source": caller,
                    "target": callee,
                    "target_parameters": self.symbols[callee]["parameters"],
                    "call_sites": sites,
                }
            )
        return {
            "found": bool(path),
            "symbols": path,
            "steps": steps,
            "scope": "One shortest resolved call chain, with all indexed call sites per step. "
            "Arguments are source expressions, not observed runtime values; "
            "parameter ordering alone does not bind keywords, splats, or implicit receivers.",
        }

    def _build_hierarchies(self):
        self.hierarchies = {
            symbol["id"]: {
                "symbol": symbol,
                "bases": symbol["bases"],
                "base_links": base_links(self, symbol),
                "subclasses": [],
                "candidate_subclasses": [],
                "evidence": "resolved subclasses only; uncertain base bindings retained as candidates",
            }
            for symbol in self.symbols.values()
        }
        for child in self.symbols.values():
            for link in self.hierarchies[child["id"]]["base_links"]:
                for target in link["targets"]:
                    hierarchy = self.hierarchies[target]
                    if link["resolution"] == "resolved":
                        if child not in hierarchy["subclasses"]:
                            hierarchy["subclasses"].append(child)
                    else:
                        hierarchy["candidate_subclasses"].append({"symbol": child, "base": link})

    def get_hierarchy(self, symbol: str) -> dict:
        return self.hierarchies[self.get_definition(symbol)["id"]]

    def profile(self, symbol: str) -> dict:
        definition = self.get_definition(symbol)
        return {
            "definition": definition,
            "callers": self.get_callers(definition["id"]),
            "calls": [c for c in self.calls if c["caller"] == definition["id"]],
            "hierarchy": self.get_hierarchy(definition["id"]),
            "runtime_calls": [
                edge for edge in self.runtime_edges() if edge["source"] == definition["id"]
            ],
        }

    def runtime_edges(self) -> list[dict]:
        trace = self.state.artifact("trace", "last") if self.state else None
        if not trace:
            return []
        symbols = {
            (s["path"], s["name"], s["line"]): s["id"]
            for s in self.symbols.values()
            if self.files[s["path"]].get("digest") == trace.get("source_digests", {}).get(s["path"])
        }
        frames, edges = {}, []
        for event in trace["events"]:
            if event["event"] != "call":
                continue
            identity = symbols.get((event["path"], event["function"], event["definition_line"]))
            frames[event["frame"]] = identity
            source = frames.get(event["parent_frame"])
            if source and identity:
                edges.append(
                    {
                        "source": source,
                        "target": identity,
                        "evidence": "runtime observation",
                        "arguments": event["arguments"],
                    }
                )
        return edges
