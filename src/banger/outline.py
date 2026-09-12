"""Compact, one-level outlines from parsed declaration bodies."""


def source_outline(declaration, body, source, expression_body=False):
    def entry(node, stop=None):
        end = node.end_byte if stop is None else stop
        newline = source.find(b"\n", node.start_byte, end)
        if newline >= 0:
            end = newline
        value = source[node.start_byte : end].decode("utf-8", errors="replace").strip()
        return {
            "kind": node.type,
            "line": node.start_point.row + 1,
            "end_line": node.end_point.row + 1,
            "text": value[:240],
            "text_truncated": len(value) > 240,
        }

    statements = []
    if body:
        if expression_body:
            statements = [body]
        else:
            for child in body.named_children:
                if child.type == "statement_list":
                    statements.extend(child.named_children)
                else:
                    statements.append(child)
    return {
        "outline": [entry(declaration, body.start_byte if body else None)]
        + [entry(node) for node in statements[:99]],
        "truncated": len(statements) > 99,
        "total_entries": len(statements) + 1,
    }
