"""Syntactic DOM-call candidates in JavaScript and TypeScript."""

from tree_sitter_language_pack import get_parser

from banger.index import text, walk
from banger.javascript_literals import string_value


def references(source, path, language="javascript", line=1, source_lines=None):
    data = source.encode("utf-8")
    tree = get_parser(language).parse(data)
    for node in walk(tree.root_node):
        if node.type != "call_expression" or node.has_error:
            continue
        function = node.child_by_field_name("function")
        arguments = node.child_by_field_name("arguments")
        if function is None or arguments is None:
            continue
        if function.type == "subscript_expression":
            method = string_value(function.child_by_field_name("index"))
        else:
            method = text(
                function.child_by_field_name("property")
                if function.type == "member_expression"
                else function
            )
        if method not in {
            "querySelector",
            "querySelectorAll",
            "getElementById",
        }:
            continue
        values = [child for child in arguments.named_children if child.type != "comment"]
        if len(values) != 1:
            continue
        selector = string_value(values[0])
        if selector is None:
            continue
        if method == "getElementById":
            selector = "#" + selector
        position = len(data[: node.start_byte].decode("utf-8"))
        yield {
            "selector": selector,
            "path": path,
            "line": source_lines[position]
            if source_lines is not None
            else line + node.start_point.row,
            "resolution": "syntactic candidate",
        }
