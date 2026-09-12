"""Extract Python literal documents and unevaluated f-string template skeletons."""

import ast
import re

from banger.literal_map import literal_lines


def python_fragments(source, path):
    fragments = []

    def visit(node):
        if isinstance(node, ast.JoinedStr):
            expressions = [
                ast.unparse(part.value)
                for part in ast.walk(node)
                if isinstance(part, ast.FormattedValue)
            ]
            content = "".join(
                part.value if isinstance(part, ast.Constant) else f"__banger_interpolation_{i}__"
                for i, part in enumerate(node.values)
            )
            mapping = None
            kind = "fstring"
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            content, expressions = node.value, []
            mapping = literal_lines(source, node)
            kind = "string"
        else:
            for child in ast.iter_child_nodes(node):
                visit(child)
            return
        if re.search(r"<[a-zA-Z]", content) or expressions and "<" in content:
            identity = f"{path}:{kind}:{node.lineno}:{node.col_offset}"
            unresolved = (
                [
                    {
                        "document": identity,
                        "path": path,
                        "line": node.lineno,
                        "expressions": expressions,
                        "reason": "Dynamic template skeleton; interpolation can alter text, attributes, styles or element structure",
                    }
                ]
                if expressions
                else []
            )
            fragments.append((identity, content, node.lineno - 1, mapping, unresolved))

    visit(ast.parse(source))
    return fragments
