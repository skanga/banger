"""Source-only argument binding for flow queries; never evaluates expressions."""

import ast
import inspect


def parameter_names(definition):
    if "signature_parameters" in definition:
        return [p["name"] for p in definition["signature_parameters"]]
    return definition.get("parameters", [])


def bind_arguments(definition, call):
    if not definition["path"].endswith(".py"):
        return {
            name: [argument]
            for name, argument in zip(parameter_names(definition), call["arguments"])
        }, "positional approximation"
    if "signature_parameters" not in definition:
        return {}, "unresolved"
    try:
        expression = ast.parse(call["expression"], mode="eval").body
    except SyntaxError:
        return {}, "unresolved"
    if (
        not isinstance(expression, ast.Call)
        or any(isinstance(a, ast.Starred) for a in expression.args)
        or any(k.arg is None for k in expression.keywords)
    ):
        return {}, "unresolved"
    parameters = definition["signature_parameters"]
    if call.get("evidence", "").startswith("implicit receiver hierarchy candidates"):
        parameters = [p for p in parameters if p["name"] != definition.get("implicit_receiver")]
    signature = inspect.Signature(
        [
            inspect.Parameter(
                p["name"],
                getattr(inspect.Parameter, p["kind"]),
                default=inspect.Parameter.empty if p["required"] else None,
            )
            for p in parameters
        ]
    )

    def source(node):
        return ast.get_source_segment(call["expression"], node) or ast.unparse(node)

    try:
        bound = signature.bind(
            *[source(a) for a in expression.args],
            **{k.arg: source(k.value) for k in expression.keywords},
        )
    except TypeError:
        return {}, "invalid call"
    return {
        name: list(value.values())
        if isinstance(value, dict)
        else list(value)
        if isinstance(value, tuple)
        else [value]
        for name, value in bound.arguments.items()
    }, "signature"
