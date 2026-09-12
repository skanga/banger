"""Syntactic Python expression reads with lambda and comprehension scopes."""

import ast


def assignment_names(node):
    if isinstance(node, ast.Lambda):
        children = [n for n in node.args.defaults + node.args.kw_defaults if n is not None]
    else:
        children = ast.iter_child_nodes(node)
    names = {node.target.id} if isinstance(node, ast.NamedExpr) else set()
    for child in children:
        names.update(assignment_names(child))
    return names


def python_reads(content):
    try:
        root = ast.parse(content, mode="eval").body
    except (SyntaxError, ValueError):
        return set()
    reads = set()

    def visit(node, bound):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load) and node.id not in bound:
                reads.add(node.id)
            return
        if isinstance(node, ast.Lambda):
            for default in node.args.defaults + node.args.kw_defaults:
                if default is not None:
                    visit(default, bound)
            args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
            args += [a for a in (node.args.vararg, node.args.kwarg) if a is not None]
            visit(node.body, bound | {a.arg for a in args} | assignment_names(node.body))
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            local = bound | {
                name.id
                for generator in node.generators
                for name in ast.walk(generator.target)
                if isinstance(name, ast.Name)
            }
            for position, generator in enumerate(node.generators):
                visit(generator.iter, bound if position == 0 else local)
                for condition in generator.ifs:
                    visit(condition, local)
            if isinstance(node, ast.DictComp):
                visit(node.key, local)
                visit(node.value, local)
            else:
                visit(node.elt, local)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, bound)

    visit(root, set())
    return reads
