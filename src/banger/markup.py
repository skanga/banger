"""Document-scoped HTML, CSS and DOM reference analysis."""

import re
from html.parser import HTMLParser
from itertools import pairwise
from pathlib import Path

from tree_sitter_language_pack import get_parser

from banger.css_attributes import ATTRIBUTE, attribute_matches
from banger.css_imports import import_path
from banger.css_variables import CSSVariables
from banger.discovery import discover_files
from banger.index import text
from banger.python_markup import python_fragments

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
    def __init__(self, path, identity, offset=0, source="", source_lines=None, unresolved=None):
        super().__init__(convert_charrefs=True)
        self.path, self.identity, self.source_offset = path, identity, offset
        self.nodes, self.stack, self.resources = [], [], []
        self.style = None
        self.unresolved = unresolved or []
        self.source_lines = source_lines
        self.line_starts = [0] + [i + 1 for i, char in enumerate(source) if char == "\n"]

    def _source_position(self):
        row, column = self.getpos()
        return self.line_starts[row - 1] + column

    def _source_line(self):
        if self.source_lines is not None:
            return self.source_lines[self._source_position()]
        return self.getpos()[0] + self.source_offset

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        node = {
            "id": f"{self.identity}:element:{len(self.nodes)}",
            "tag": tag,
            "attributes": attributes,
            "parent": self.stack[-1] if self.stack else None,
            "path": self.path,
            "document": self.identity,
            "line": self._source_line(),
            "dynamic": bool(self.unresolved),
            "source_mapping": "exact literal"
            if self.source_lines is not None
            else "source text"
            if self.path.endswith((".html", ".htm"))
            else "approximate fragment",
        }
        self.nodes.append(node)
        relations = set(re.findall(r"[^ \t\r\n\f]+", (attributes.get("rel") or "").lower()))
        stylesheet = tag == "style" or (
            tag == "link" and "stylesheet" in relations and attributes.get("href")
        )
        restriction = None
        if stylesheet:
            media = (attributes.get("media") or "").strip(" \t\r\n\f")
            if tag == "link" and "disabled" in attributes:
                restriction = "Disabled stylesheet link is not applied"
            elif tag == "link" and "alternate" in relations:
                restriction = "Alternate stylesheet selection is unresolved"
            elif media.lower() not in {"", "all"}:
                restriction = "Conditional stylesheet media is unresolved: " + media
            if restriction:
                self.resources.append(("unresolved", restriction, node["line"], None))
            elif tag == "link":
                self.resources.append(("link", attributes["href"], node["line"], None))
        if tag == "style" and not restriction:
            self.style = []
            self.style_lines = []
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
            self.resources.append(
                ("inline", "".join(self.style), self.style_line, self.style_lines)
            )
            self.style = None
        for index in range(len(self.stack) - 1, -1, -1):
            identity = self.stack[index]
            if next(n for n in self.nodes if n["id"] == identity)["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.style is not None:
            self.style.append(data)
            if self.source_lines is not None:
                start = self._source_position()
                self.style_lines.extend(self.source_lines[start : start + len(data)])
            else:
                line = self.getpos()[0] + self.source_offset
                for char in data:
                    self.style_lines.append(line)
                    line += char == "\n"


class MarkupIndex:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.nodes, self.documents, self.rules, self.references = {}, {}, {}, []
        self.previous_siblings = {}
        self.unresolved = []

    def refresh(self):
        self._style_cache = {}
        self.nodes, self.documents, self.rules, self.references = {}, {}, {}, []
        self.previous_siblings = {}
        self.unresolved = []
        visible_files = set(discover_files(self.root))
        self._visible_files = visible_files
        for path in sorted(visible_files):
            if path.suffix not in {".html", ".htm", ".py", ".js", ".ts", ".jsx", ".tsx"}:
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            relative = path.relative_to(self.root).as_posix()
            fragments = (
                [(relative, source, 0, None, [])] if path.suffix in {".html", ".htm"} else []
            )
            if path.suffix == ".py":
                try:
                    fragments.extend(python_fragments(source, relative))
                except SyntaxError:
                    pass
            for identity, fragment, offset, source_lines, unresolved in fragments:
                doc = Document(relative, identity, offset, fragment, source_lines, unresolved)
                doc.feed(fragment)
                self.unresolved.extend(unresolved)
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
            self._imports_remaining = 1000
            for kind, value, line, source_lines in document.resources:
                if kind == "unresolved":
                    self.rules[identity].append(
                        {"unresolved": value, "path": document.path, "line": line}
                    )
                    continue
                if kind == "inline":
                    css, source = value, document.path
                else:
                    target = ((self.root / document.path).parent / value.split("?", 1)[0]).resolve()
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
                self.rules[identity].extend(self._css(css, source, line, source_lines))
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

    def _import_css(self, statement, path, ancestry):
        target = ((self.root / path).parent / import_path(statement)).resolve()
        if target not in self._visible_files or not target.is_file():
            raise ValueError("Unavailable imported stylesheet")
        relative = target.relative_to(self.root).as_posix()
        if relative in ancestry:
            raise ValueError("CSS import cycle")
        if len(ancestry) >= 32 or self._imports_remaining <= 0:
            raise ValueError("CSS import expansion limit reached")
        self._imports_remaining -= 1
        return self._css(
            target.read_text(encoding="utf-8"), relative, 1, ancestry=(*ancestry, relative)
        )

    def _css(self, source, path, line, source_lines=None, ancestry=None):
        tree = get_parser("css").parse(source.encode())
        byte_lines = (
            [origin for char, origin in zip(source, source_lines) for _ in char.encode("utf-8")]
            if source_lines is not None
            else None
        )
        rules = []
        imports_allowed = True
        ancestry = ancestry or (path,)
        for node in tree.root_node.named_children:
            if node.type == "import_statement":
                try:
                    if not imports_allowed:
                        raise ValueError("CSS import appears after other rules")
                    rules.extend(self._import_css(text(node), path, ancestry))
                except (ValueError, OSError) as exc:
                    rules.append(
                        {
                            "unresolved": text(node),
                            "reason": str(exc),
                            "path": path,
                            "line": byte_lines[node.start_byte]
                            if byte_lines
                            else line + node.start_point.row,
                        }
                    )
                continue
            if node.type not in {"comment", "charset_statement"} and not re.fullmatch(
                r"@layer\s+[^{};]+;", text(node), re.IGNORECASE
            ):
                imports_allowed = False
            if node.type != "rule_set":
                if node.type != "comment":
                    rules.append(
                        {
                            "unresolved": text(node),
                            "path": path,
                            "line": byte_lines[node.start_byte]
                            if byte_lines
                            else line + node.start_point.row,
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
                        "line": byte_lines[node.start_byte]
                        if byte_lines
                        else line + node.start_point.row,
                    }
                )
        return rules

    @staticmethod
    def _parts(selector):
        # Explicit subset: simple compounds with descendant, child and sibling combinators.
        if re.search(r"[:,\\]", ATTRIBUTE.sub("", selector)):
            raise ValueError("Dynamic/complex selector is not statically evaluated: " + selector)
        parts = re.findall(rf"(?:{ATTRIBUTE.pattern}|[^\s>+~])+|[>+~]", selector.strip())
        combinators = {">", "+", "~"}
        if parts and (
            parts[0] in combinators
            or parts[-1] in combinators
            or any(a in combinators and b in combinators for a, b in pairwise(parts))
        ):
            raise ValueError("Incomplete selector: " + selector)
        return parts

    def _simple(self, selector, node):
        attrs = [
            attribute_matches(attribute, node["attributes"])
            for attribute in ATTRIBUTE.findall(selector)
        ]
        rest = ATTRIBUTE.sub("", selector)
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
        return all(attrs)

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
        without_attrs = ATTRIBUTE.sub("", selector)
        ids = len(re.findall(r"#[\w-]+", without_attrs))
        classes = len(re.findall(r"\.[\w-]+", without_attrs)) + len(ATTRIBUTE.findall(selector))
        tags = sum(
            bool(re.match(r"^[a-zA-Z][\w-]*", part))
            for part in re.split(r"\s+|[>+~]", without_attrs)
        )
        return ids, classes, tags

    def styles(self, identity):
        if identity in self._style_cache:
            return self._style_cache[identity]
        node = self.nodes[identity]
        winners, unresolved = {}, list(self.documents[node["document"]].unresolved)
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
            "scope": "Resolved author declarations and common inheritance; no layout, shorthand expansion, or browser defaults"
            + (
                "; dynamic template results are static candidates, not final runtime styles"
                if node["dynamic"]
                else ""
            ),
        }
        self._style_cache[identity] = result
        return result

    def dom_references(self, selector):
        return [r for r in self.references if r["selector"] == selector]
