"""Persist Python compiler scope classifications without executing project code."""

import symtable


def annotate_value_scopes(data, path, symbols):
    try:
        root = symtable.symtable(data, path, "exec")
    except (SyntaxError, ValueError):
        return
    definitions = {(s["name"], s["line"]): s for s in symbols}

    def visit(table, ancestors):
        owner = (
            definitions.get((table.get_name(), table.get_lineno()))
            if isinstance(table, (symtable.Function, symtable.Class))
            else None
        )
        if owner:
            scopes = {}
            for binding in table.get_symbols():
                name = binding.get_name()
                if binding.is_global():
                    scopes[name] = None
                elif binding.is_local():
                    scopes[name] = owner["id"]
                elif binding.is_free() or binding.is_nonlocal():
                    for enclosing, definition in reversed(ancestors):
                        if not isinstance(enclosing, symtable.Function):
                            continue
                        if (
                            name in enclosing.get_identifiers()
                            and enclosing.lookup(name).is_local()
                        ):
                            if definition:
                                scopes[name] = definition["id"]
                            break
            owner["python_value_scopes"] = scopes
        for child in table.get_children():
            visit(child, [*ancestors, (table, owner)])

    visit(root, [])
