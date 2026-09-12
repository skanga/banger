"""Document-scoped HTML, CSS and DOM reference analysis."""

import ast
import re
from html.parser import HTMLParser
from itertools import pairwise
from pathlib import Path

from tree_sitter_language_pack import get_parser

from banger.css_variables import CSSVariables
from banger.discovery import discover_files
from banger.index import text

INHERITED = {
    "color",
    "font",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "line-height",
    "text-align",
    "text-indent",
    "text-transform",
    "visibility",
    "cursor",
    "direction",
    "letter-spacing",
    "word-spacing",
    "white-space",
    "list-style",
    "list-style-type",
    "list-style-position",
    "border-collapse",
}


class Document(HTMLParser):
    def __init__(self, path, identity, offset=0):
        super().__init__(convert_charrefs=True)
        self.path, self.identity, self.source_offset = path, identity, offset
        self.nodes, self.stack, self.resources = [], [], []
        self.style = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        node = {
            "id": f"{self.identity}:element:{len(self.nodes)}",
            "tag": tag,
            "attributes": attributes,
            "parent": self.stack[-1] if self.stack else None,
            "path": self.path,
            "document": self.identity,
            "line": self.getpos()[0] + self.source_offset,
        }
        self.nodes.append(node)
        if tag == "link" and attributes.get("rel") == "stylesheet" and attributes.get("href"):
            self.resources.append(("link", attributes["href"], node["line"]))
        if tag == "style":
            self.style = []
            self.style_line = node["line"] + self.get_starttag_text().count("\n")
        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self.stack.append(node["id"])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "style" and self.style is not None:
            self.resources.append(("inline", "".join(self.style), self.style_line))
            self.style = None
        for index in range(len(self.stack) - 1, -1, -1):
            identity = self.stack[index]
            if next(n for n in self.nodes if n["id"] == identity)["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.style is not None:
            self.style.append(data)


class MarkupIndex:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.nodes, self.documents, self.rules, self.references = {}, {}, {}, []
        self.previous_siblings = {}

    def refresh(self):
        self._style_cache = {}
        self.nodes, self.documents, self.rules, self.references = {}, {}, {}, []
        self.previous_siblings = {}
        visible_files = set(discover_files(self.root))
        for path in sorted(visible_files):
            if path.suffix not in {".html", ".htm", ".py", ".js", ".ts", ".jsx", ".tsx"}:
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            relative = path.relative_to(self.root).as_posix()
            fragments = [(relative, source, 0)] if path.suffix in {".html", ".htm"} else []
            if path.suffix == ".py":
                try:
                    for node in ast.walk(ast.parse(source)):
                        if (
                            isinstance(node, ast.Constant)
                            and isinstance(node.value, str)
                            and re.search(r"<[a-zA-Z]", node.value)
                        ):
                            fragments.append(
                                (
                                    f"{relative}:string:{node.lineno}",
                                    node.value,
                                    node.lineno - 1,
                                )
                            )
                except SyntaxError:
                    pass
            for identity, fragment, offset in fragments:
                doc = Document(relative, identity, offset)
                doc.feed(fragment)
                self.documents[identity] = doc
                self.nodes.update({n["id"]: n for n in doc.nodes})
                previous = {}
                for node in doc.nodes:
                    self.previous_siblings[node["id"]] = previous.get(node["parent"])
                    previous[node["parent"]] = node["id"]
            for match in re.finditer(
                r"""(?:querySelector(All)?|getElementById)\s*\(\s*(["'])(.*?)\2\s*\)""", source
            ):
                selector = match.group(3)
                if match.group().startswith("getElementById"):
                    selector = "#" + selector
                self.references.append(
                    {
                        "selector": selector,
                        "path": relative,
                        "line": source.count("\n", 0, match.start()) + 1,
                    }
                )
        for identity, document in self.documents.items():
            self.rules[identity] = []
            for kind, value, line in document.resources:
                if kind == "inline":
                    css, source = value, document.path
                else:
                    target = (self.root / document.path).parent / value.split("?", 1)[0]
                    if target.resolve() not in visible_files or not target.is_file():
                        self.rules[identity].append(
                            {"unresolved": "Unavailable stylesheet " + value}
                        )
                        continue
                    css, source = (
                        target.read_text(encoding="utf-8"),
                        target.relative_to(self.root).as_posix(),
                    )
                    line = 1
                self.rules[identity].extend(self._css(css, source, line))
        return {"documents": len(self.documents), "elements": len(self.nodes)}

    @staticmethod
    def _declarations(node):
        declarations = []
        for child in node.named_children:
            if child.type != "declaration":
                continue
            prop = next((n for n in child.named_children if n.type == "property_name"), None)
            if prop:
                value = (
                    text(child)[len(text(prop)) :]
                    .lstrip()
                    .removeprefix(":")
                    .strip()
                    .rstrip(";")
                    .strip()
                )
                important = bool(re.search(r"!important\s*$", value, re.IGNORECASE))
                value = re.sub(r"\s*!important\s*$", "", value, flags=re.IGNORECASE)
                declarations.append(
                    {
                        "property": text(prop)
                        if text(prop).startswith("--")
                        else text(prop).lower(),
                        "value": value,
                        "important": important,
                    }
                )
        return declarations

    def _css(self, source, path, line):
        tree = get_parser("css").parse(source.encode())
        rules = []
        for node in tree.root_node.named_children:
            if node.type != "rule_set":
                if node.type != "comment":
                    rules.append(
                        {
                            "unresolved": text(node),
                            "path": path,
                            "line": line + node.start_point.row,
                        }
                    )
                continue
            selectors = next((n for n in node.named_children if n.type == "selectors"), None)
            block = next((n for n in node.named_children if n.type == "block"), None)
            if not block or not selectors:
                continue
            for selector in selectors.named_children:
                rules.append(
                    {
                        "selector": text(selector),
                        "declarations": self._declarations(block),
                        "path": path,
                        "line": line + node.start_point.row,
                    }
                )
        return rules

    @staticmethod
    def _parts(selector):
        # Explicit subset: simple compounds with descendant, child and sibling combinators.
        if re.search(r"[:,\\]", selector):
            raise ValueError("Dynamic/complex selector is not statically evaluated: " + selector)
        parts = re.findall(r"(?:\[[^\]]*\]|[^\s>+~])+|[>+~]", selector.strip())
        combinators = {">", "+", "~"}
        if parts and (
            parts[0] in combinators
            or parts[-1] in combinators
            or any(a in combinators and b in combinators for a, b in pairwise(parts))
        ):
            raise ValueError("Incomplete selector: " + selector)
        return parts

    def _simple(self, selector, node):
        attrs = []
        for attribute in re.findall(r"\[[^\]]*\]", selector):
            match = re.fullmatch(
                r"""\[\s*([\w-]+)\s*(?:=\s*(?:"([^"]*)"|'([^']*)'|([^\s\]"']+))\s*)?\]""",
                attribute,
            )
            if not match:
                raise ValueError("Unsupported attribute selector: " + attribute)
            name, *values = match.groups()
            attrs.append((name, next((v for v in values if v is not None), None)))
        rest = re.sub(r"\[[^\]]*\]", "", selector)
        if not re.fullmatch(r"(?:[\w*-]+)?(?:[.#][\w-]+)*", rest):
            raise ValueError("Unsupported selector: " + selector)
        tag = re.match(r"^[\w*-]+", rest)
        if tag and tag.group() not in {"*", node["tag"]}:
            return False
        attributes = node["attributes"]
        if any(attributes.get("id") != identity for identity in re.findall(r"#([\w-]+)", rest)):
            return False
        if not set(re.findall(r"\.([\w-]+)", rest)).issubset(
            (attributes.get("class") or "").split()
        ):
            return False
        return all(
            name in attributes and (value is None or attributes[name] == value)
            for name, value in attrs
        )

    def matches(self, selector, node):
        if selector.strip() == ":root":
            return node["tag"] == "html" and node["parent"] is None
        parts = self._parts(selector)
        if not parts:
            return False

        def match(index, element):
            if not self._simple(parts[index], element):
                return False
            if index == 0:
                return True
            if parts[index - 1] in {"+", "~"}:
                sibling = self.nodes.get(self.previous_siblings[element["id"]])
                while sibling:
                    if match(index - 2, sibling):
                        return True
                    if parts[index - 1] == "+":
                        break
                    sibling = self.nodes.get(self.previous_siblings[sibling["id"]])
                return False
            parent = self.nodes.get(element["parent"])
            if parts[index - 1] == ">":
                return bool(parent and index >= 2 and match(index - 2, parent))
            while parent:
                if match(index - 1, parent):
                    return True
                parent = self.nodes.get(parent["parent"])
            return False

        return match(len(parts) - 1, node)

    def query(self, selector):
        return [n for n in self.nodes.values() if self.matches(selector, n)]

    @staticmethod
    def specificity(selector):
        if selector.strip() == ":root":
            return 0, 1, 0
        without_attrs = re.sub(r"\[[^\]]*\]", "", selector)
        ids = len(re.findall(r"#[\w-]+", without_attrs))
        classes = len(re.findall(r"\.[\w-]+", without_attrs)) + selector.count("[")
        tags = sum(
            bool(re.match(r"^[a-zA-Z][\w-]*", part))
            for part in re.split(r"\s+|[>+~]", without_attrs)
        )
        return ids, classes, tags

    def styles(self, identity):
        if identity in self._style_cache:
            return self._style_cache[identity]
        node = self.nodes[identity]
        winners, unresolved = {}, []
        for order, rule in enumerate(self.rules[node["document"]]):
            if "unresolved" in rule:
                unresolved.append(rule)
                continue
            try:
                matched = self.matches(rule["selector"], node)
            except ValueError as exc:
                unresolved.append(
                    {
                        "selector": rule["selector"],
                        "reason": str(exc),
                        "path": rule["path"],
                        "line": rule["line"],
                    }
                )
                continue
            if matched:
                for declaration in rule["declarations"]:
                    rank = (declaration["important"], 0, *self.specificity(rule["selector"]), order)
                    prop = declaration["property"]
                    if prop not in winners or rank >= winners[prop][0]:
                        winners[prop] = (
                            rank,
                            {
                                **declaration,
                                "selector": rule["selector"],
                                "path": rule["path"],
                                "line": rule["line"],
                            },
                        )
        inline = node["attributes"].get("style")
        if inline:
            declarations = self._css("x {" + inline + "}", node["path"], node["line"])
            for rule in declarations:
                for declaration in rule.get("declarations", []):
                    rank = (declaration["important"], 1, 0, 0, 0, 0)
                    prop = declaration["property"]
                    if prop not in winners or rank >= winners[prop][0]:
                        winners[prop] = (
                            rank,
                            {
                                **declaration,
                                "selector": "inline style",
                                "path": node["path"],
                                "line": node["line"],
                            },
                        )
        computed = {p: dict(v[1]) for p, v in winners.items()}
        inherited = self.styles(node["parent"])["computed"] if node["parent"] else {}
        for prop, declaration in inherited.items():
            if (prop in INHERITED or prop.startswith("--")) and prop not in computed:
                computed[prop] = {**declaration, "inherited_from": node["parent"]}

        for prop, declaration in list(computed.items()):
            value = declaration["value"]
            if (
                value == "inherit"
                or value == "unset"
                and (prop in INHERITED or prop.startswith("--"))
            ):
                if prop in inherited:
                    computed[prop] = {**inherited[prop], "inherited_from": node["parent"]}
                else:
                    computed.pop(prop)
                    unresolved.append(
                        {"property": prop, "reason": "Browser initial value required"}
                    )
            elif value in {"initial", "unset", "revert", "revert-layer"}:
                computed.pop(prop)
                unresolved.append(
                    {"property": prop, "reason": "Browser initial/origin/layer value required"}
                )
        variables = CSSVariables({p: d["value"] for p, d in computed.items() if p.startswith("--")})
        for prop, declaration in list(computed.items()):
            try:
                declaration["value"] = (
                    variables.resolve(prop)
                    if prop.startswith("--")
                    else variables.substitute(declaration["value"])
                )
            except ValueError as exc:
                computed.pop(prop)
                unresolved.append({"property": prop, "reason": str(exc)})
        result = {
            "element": node,
            "computed": computed,
            "unresolved": unresolved,
            "scope": "Resolved author declarations and common inheritance; no layout, shorthand expansion, or browser defaults",
        }
        self._style_cache[identity] = result
        return result

    def dom_references(self, selector):
        return [r for r in self.references if r["selector"] == selector]
